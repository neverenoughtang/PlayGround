import os, sys, json, time
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from utils.llm_models import load_model
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.fault_diagnose_rag import FaultDiagnosisKnowledgeBase

_MCP_TOOLS_CACHE = None
_MCP_CLIENT = None
_GLOBAL_EXPERIENCE_RAG_CACHE = None

async def get_mcp_tools(lab_name: str):
    global _MCP_TOOLS_CACHE, _MCP_CLIENT
    if _MCP_TOOLS_CACHE is not None:
        return _MCP_TOOLS_CACHE
    
    mcp_server_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../mcp_server")
    custom_env = os.environ.copy()
    custom_env["LAB_NAME"] = lab_name
    server_path = os.path.join(mcp_server_dir, "klonet_server.py")
    
    connections = {
        "klonet_server": {
            "command": sys.executable, 
            "args": [server_path],
            "transport": "stdio", 
            "env": custom_env
        }
    }
    _MCP_CLIENT = MultiServerMCPClient(connections)
    _MCP_TOOLS_CACHE = await _MCP_CLIENT.get_tools()
    return _MCP_TOOLS_CACHE

async def cleanup_mcp_client():
    global _MCP_CLIENT, _MCP_TOOLS_CACHE
    if _MCP_CLIENT is not None:
        _MCP_CLIENT = None
        _MCP_TOOLS_CACHE = None


async def prewarm_diagnose_caches(lab_name: str):
    """
    【新增】全局缓存预热函数。
    在诊断图 (Graph) 启动前调用，提前启动 MCP Server 并将 RAG 向量库加载到内存中，
    消除 Agent 第一次调用时的冷启动延迟。
    """
    global _MCP_TOOLS_CACHE, _GLOBAL_EXPERIENCE_RAG_CACHE
    print("🔥 [系统预热] 正在预热底层工具与知识库缓存...")
    
    # 1. 预热 MCP 工具
    if _MCP_TOOLS_CACHE is None:
        _MCP_TOOLS_CACHE = await get_mcp_tools(lab_name)
        print("   ✅ MCP 工具预加载完成")
        
    # 2. 预热智慧导师的 RAG 知识库
    if _GLOBAL_EXPERIENCE_RAG_CACHE is None:
        _GLOBAL_EXPERIENCE_RAG_CACHE = FaultDiagnosisKnowledgeBase(force_rebuild=False)
        print("   ✅ RAG 故障诊断知识库预加载完成")


async def create_smart_tools(state: dict):
    """
    构建属于 Worker 的完整工具箱，包含基础 MCP 和高级整合工具
    """
    mcp_tools = await get_mcp_tools(state["lab_name"])
    
    @tool
    async def global_inspector_tool() -> str:
        """
        【全局网络体检】
        后台并发收集全网 Ping、ARP表、接口状态与 FRR 邻居状态，并输出摘要。初期诊断必用！
        """
        # 从 mcp_tools 中获取底层函数执行
        tool_map = {t.name: t for t in mcp_tools}
        try:
            ping_res = await tool_map["get_reachability"].ainvoke({})
            arp_res = await tool_map["check_arp"].ainvoke({"node_names": "all"})
            iface_res = await tool_map["check_interface"].ainvoke({"node_names": "all"})
            frr_res = await tool_map["check_frr"].ainvoke({"node_names": "all"})
        except Exception as e:
            return f"[Inspector 异常] {e}"

        raw_info = f"[Ping]\n{ping_res}\n\n[ARP]\n{arp_res}\n\n[Interface]\n{iface_res}\n\n[FRR]\n{frr_res}"
        
        # 使用 LLM 对繁杂数据进行结构化摘要
        llm = load_model(backend_model=state["backend_model"])
        prompt = f"网络场景：{state['lab_name']}。请基于以下全网状态数据，总结出异常点(如哪些节点ping不通、谁的网卡DOWN了、谁的路由邻居Idle)。只输出异常点，完全正常的部分请忽略。\n{raw_info[:5000]}"
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        return f"【全局体检异常报告】:\n{res.content}"

    @tool
    async def smart_mentor_tool(current_blocker: str, knowledge_count: int = 5, experience_count: int = 3) -> str:
        """【智慧导师】
        困惑时调用。输入你当前的卡点、所需的固定手册条数与成功经验条数，导师将给出诊断建议。"""
        global _GLOBAL_EXPERIENCE_RAG_CACHE
        
        # 移除原先的延迟加载逻辑，直接使用预热好的全局单例
        if _GLOBAL_EXPERIENCE_RAG_CACHE is None:
            # 仅作极端的兜底保护
            _GLOBAL_EXPERIENCE_RAG_CACHE = FaultDiagnosisKnowledgeBase(force_rebuild=False)
            
        rag_info = _GLOBAL_EXPERIENCE_RAG_CACHE.search(
            query=f"{state['problem_info']}。卡点：{current_blocker}",
            current_scenario=state["lab_name"],
            final_k=knowledge_count
        )
        
        mysql_db = DiagnoseExperienceBase() # MySQL连接池通常自带连接管理，无需强行全局预热
        sql_info = await mysql_db.search(state["lab_name"], state["problem_info"], limit=experience_count)
        
        llm = load_model(backend_model=state["backend_model"])
        prompt = f"你是网络排障导师。学生遇到卡点：{current_blocker}。用户投诉：{state['problem_info']}。结合以下手册和经验，给出最符合当前情境的 2 条具体排查命令或方向建议。\n手册：{rag_info[:1500]}\n历史：{sql_info[:1500]}"
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        return f"【导师建议】: {res.content}"

    @tool
    def submit_diagnosis(faults_json_str: str) -> str:
        """
        确诊故障后提交结果。必须传入规范的 JSON 字符串映射。
        例如：'{"link_loss": ["h1", "h3"], "frr_service_down": ["r2"]}'
        如果你的假设域内没发现故障，可提交 '{}'。
        """
        return f"[DIAGNOSIS_SUBMITTED] {faults_json_str}"

    return mcp_tools + [global_inspector_tool, smart_mentor_tool, submit_diagnosis]