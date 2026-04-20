import os, sys, time
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from utils.llm_models import load_model
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.fault_diagnose_rag import FaultDiagnosisKnowledgeBase

# 【核心修复】：改为字典缓存
_MCP_CLIENTS = {}
_MCP_TOOLS_CACHE = {}
_GLOBAL_EXPERIENCE_RAG_CACHE = None
_GLOBAL_EXPERIENCE_SQL_CACHE = None  # 👇 新增 SQL 缓存变量

async def prewarm_diagnose_caches(lab_name: str):
    """
    【极速热启动】
    在系统启动时一次性加载底层大模型、向量库及 MCP 客户端。
    """
    global _MCP_TOOLS_CACHE, _MCP_CLIENTS, _GLOBAL_EXPERIENCE_RAG_CACHE, _GLOBAL_EXPERIENCE_SQL_CACHE
    print("🔥 [系统预热] 正在预热诊断层工具与知识库缓存...")
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
        
    if _GLOBAL_EXPERIENCE_RAG_CACHE is None:
        _GLOBAL_EXPERIENCE_RAG_CACHE = FaultDiagnosisKnowledgeBase(force_rebuild=False)
        print("   ✅ 诊断 RAG 向量数据库预加载完成")

    # 👇 新增 MySQL 经验库的热启动初始化
    if _GLOBAL_EXPERIENCE_SQL_CACHE is None:
        _GLOBAL_EXPERIENCE_SQL_CACHE = DiagnoseExperienceBase()
        print("   ✅ 诊断 MySQL 经验检索系统预加载完成")

async def get_mcp_tools(lab_name: str):
    """【核心修复】：传入 lab_name 获取对应的工具"""
    if lab_name not in _MCP_TOOLS_CACHE:
        await prewarm_diagnose_caches(lab_name)
    return _MCP_TOOLS_CACHE[lab_name]

async def cleanup_mcp_client():
    global _MCP_CLIENTS, _MCP_TOOLS_CACHE
    _MCP_CLIENTS.clear()
    _MCP_TOOLS_CACHE.clear()

async def create_worker_tools(lab_name: str):
    """
    动态构建派发给 Worker 的工具箱。
    注意：这里已移除全局巡检工具，因为巡检已经变为了前置的 Node。
    """
    mcp_tools = await get_mcp_tools(lab_name)
    
    @tool
    async def smart_mentor_tool(key: str, knowledge_count: int = 6, experience_count: int = 4) -> str:
        """
        【知识 & 经验查询】
        遇到排查瓶颈时调用。输入关键词句，查阅相关排障知识点和成功经验。

        Args:
            key(str): 关键词
            knowledge_count(int): 返回的知识点数量，默认为 4
            experience_count(int): 返回的成功经验数量，默认为 4
        """
        # RAG 查询知识点
        global _GLOBAL_EXPERIENCE_RAG_CACHE, _GLOBAL_EXPERIENCE_SQL_CACHE
        rag_info = _GLOBAL_EXPERIENCE_RAG_CACHE.search(
            query=key,
            current_scenario=lab_name,
            final_k=knowledge_count
        )

        # mysql 查询成功经验
        sql_info = await _GLOBAL_EXPERIENCE_SQL_CACHE.search(lab_name, key, limit=experience_count)
        
        # 拼接
        def truncate_text(text, max_len=3000):
                return text[:max_len] + "..." if len(text) > max_len else text

        clean_mysql = truncate_text(rag_info, 3000)
        clean_milvus = truncate_text(sql_info, 3000)

        knowledge_context = f"""
        【历史成功经验】:
        {clean_mysql}

        【固定诊断手册】:
        {clean_milvus}
        """

        return knowledge_context

    @tool
    def submit_diagnosis(faults_json_str: str) -> str:
        """
        【提交结果】
        必须传入严格 JSON。
        例如：'{"link_loss": ["h1", "h3"], "frr_service_down": ["r2"]}'
        """
        return f"[DIAGNOSIS_SUBMITTED] {faults_json_str}"

    return mcp_tools + [smart_mentor_tool, submit_diagnosis]