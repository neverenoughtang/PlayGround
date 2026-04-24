import asyncio
import os, sys, time
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.fault_diagnose_rag import FaultDiagnosisKnowledgeBase

# 【核心修复】改为字典缓存
_MCP_CLIENTS = {}
_MCP_TOOLS_CACHE = {}
_GLOBAL_EXPERIENCE_RAG_CACHE: DiagnoseExperienceBase | None = None
_GLOBAL_EXPERIENCE_SQL_CACHE: FaultDiagnosisKnowledgeBase | None = None  

async def prewarm_diagnose_caches(lab_name: str):
    """
    【极速热启动】
    在系统启动时一次性加载底层大模型、向量库及 MCP 客户端。
    """
    print("🔥 [系统预热] 正在预热诊断层工具与知识库缓存...")

    async def prewarm_mcp():
        """
        预热 MCP 客户端
        """
        global _MCP_TOOLS_CACHE, _MCP_CLIENTS
        if lab_name not in _MCP_TOOLS_CACHE:
            mcp_server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../mcp_server")
            custom_env = os.environ.copy()
            custom_env["LAB_NAME"] = lab_name
            custom_env.pop("PS1", None)
            server_path = os.path.join(mcp_server_dir, "klonet_server.py")
            connections = {"klonet_server": {"command": sys.executable, "args": [server_path], "transport": "stdio", "env": custom_env}}
            
            client = MultiServerMCPClient(connections)
            _MCP_CLIENTS[lab_name] = client
            _MCP_TOOLS_CACHE[lab_name] = await client.get_tools()
            print(f"   ✅ 诊断 MCP ({lab_name}) 底层工具预加载完成")
    
    async def prewarm_milvus():
        """
        预热 Milvus 数据库
        """
        global _GLOBAL_EXPERIENCE_RAG_CACHE
        if _GLOBAL_EXPERIENCE_RAG_CACHE is None:
            _GLOBAL_EXPERIENCE_RAG_CACHE = FaultDiagnosisKnowledgeBase(force_rebuild=False)
            print("   ✅ 诊断 RAG 向量数据库预加载完成")

    async def prewarm_sql():
        """
        预热 SQL 数据库
        """
        global _GLOBAL_EXPERIENCE_SQL_CACHE
        if _GLOBAL_EXPERIENCE_SQL_CACHE is None:
            _GLOBAL_EXPERIENCE_SQL_CACHE = DiagnoseExperienceBase()
            print("   ✅ 诊断 MySQL 经验检索系统预加载完成")

    tasks = [prewarm_mcp(), prewarm_milvus(), prewarm_sql()]
    await asyncio.gather(*tasks)

async def get_mcp_tools(lab_name: str):
    """【核心修复】：传入 lab_name 获取对应的工具"""
    if lab_name not in _MCP_TOOLS_CACHE:
        await prewarm_diagnose_caches(lab_name)
    return _MCP_TOOLS_CACHE[lab_name]

async def cleanup_mcp_client():
    global _MCP_CLIENTS, _MCP_TOOLS_CACHE
    _MCP_CLIENTS.clear()
    _MCP_TOOLS_CACHE.clear()

async def search_experience(lab_name: str, complaint: str, experience_count: int = 10):
    """
    【经验查询】
    查询某种故障排除的知识点以供 Superviser 使用。

    Args:
        complaint(str): 投诉
        lab_name(str): 实验场景
        experience_count(int): 返回的成功经验数量，默认为 10
    """
    global _GLOBAL_EXPERIENCE_SQL_CACHE
    return await _GLOBAL_EXPERIENCE_SQL_CACHE.search(
        lab_name=lab_name,  
        keyword=complaint, 
        limit=experience_count
    )

async def search_knowledge(fault: str, lab_name: str, knowledge_count: int = 2): 
    """
    【知识查询】
    查询某种故障排除的知识点以供 Worker 使用。

    Args:
        fault(str): 故障名
        lab_name(str): 实验场景
        knowledge_count(int): 返回的知识点数量，默认为 2
    """
    global _GLOBAL_EXPERIENCE_RAG_CACHE
    return await _GLOBAL_EXPERIENCE_RAG_CACHE.search(
        query=fault,
        current_scenario=lab_name,
        final_k=knowledge_count
    )

async def create_worker_tools(lab_name: str):
    """
    动态构建派发给 Worker 的工具箱。
    注意：这里已移除全局巡检工具，因为巡检已经变为了前置的 Node。
    """
    mcp_tools = await get_mcp_tools(lab_name)
    
    @tool
    def submit_diagnosis(existing: bool, location: list[str], reason: str) -> str:
        """
        当排查结束时，必须调用此工具提交你的诊断结论。
        Args:
            existing (bool): 是否发现了分配给你排查的故障？(True 或 False)
            location (list[str]): 发现故障的节点名列表(如 ["h1"])。若 existing 为 False，请传入空列表 []。
            reason (str): 诊断的简短理由或关键证据。
        """
        return "提交成功"

    return mcp_tools + [submit_diagnosis]