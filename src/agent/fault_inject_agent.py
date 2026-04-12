import asyncio
import os 
import sys
import time
import traceback
from typing import Dict, Any, TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))
if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

from utils.llm_models import load_model
from utils.fault_inject_rag import FaultKnowledgeBase

# ==========================================
# 1. 状态定义
# ==========================================
class InjectState(TypedDict):
    lab_name: str
    netenv_info: str
    fault_query: str
    actor_model: str
    max_steps: int
    
    inject_result: str
    problem_info: str
    expected_fault: str
    expected_location: str

# ==========================================
# 2. 三合一提交工具
# ==========================================
@tool
def submit_inject(result: str, fault_description: str, expected_fault: str, expected_location: str) -> str:
    """
    当且仅当确认故障注入完成（或彻底失败）时调用。必须且只能调用一次。
    Args:
        result: 注入结果 (成功填 successful，失败填 fatal)
        fault_description: 故障表现描述 (直接提取知识库文档中的"故障表现描述"原文)
        expected_fault: 预期故障标识 (提取知识库文档中该故障的英文标识，如 link_loss)
        expected_location: 预期故障节点位置 (填入你注入的故障节点名)
    """
    return "提交成功，任务结束..."

# ==========================================
# 3. 智能体节点 (Nodes)
# ==========================================
class FaultRetrievalAgent:
    """
    故障注入 RAG 智能体
    """
    def __init__(self):
        self.rag_agent = FaultKnowledgeBase(force_rebuild=False) 

    async def get_reference(self, query) -> Dict[str, Any]:
        inject_doc = self.rag_agent.search(query)
        return {"inject_doc": inject_doc}
        
class FaultInjectAgent:
    """
    故障注入智能体
    """
    def __init__(self, lab_name: str, max_steps: int, netenv_info: str, fault_query: str, backend_model: str = "qwen3.5-27b"):
        self.lab_name = lab_name  
        self.max_steps = max_steps
        self.netenv_info = netenv_info
        self.fault_query = fault_query
        self.llm = load_model(backend_model=backend_model)
        self.system_prompt = "" # 延迟到异步方法中加载

    async def _get_system_prompt(self) -> str:
        rag_agent = FaultRetrievalAgent()
        ref_data = await rag_agent.get_reference(self.fault_query)
        problem_doc = ref_data["inject_doc"]

        SYSTEM_PROMPT = f"""你是一名专业的网络工程师，负责在仿真网络环境中注入故障，以便学生学习网络故障诊断。

【当前网络场景】
{self.netenv_info}

【网络参数说明】
- host_name/node: 节点名，如 'h1', 'server'
- link: 链路名，不是网卡名字! 如 'l1', 'l8'
- iface: 网卡(接口)名，字符串 'to' 开头，如 'to_s1_1'
- command: 包含参数的指令，如 'ping -c 5 192.168.1.22'

【故障参考文档】
{problem_doc}

【任务】
用户需求: {self.fault_query}
严格遵循参考文档和用户需求选择工具填入参数注入故障，并使用检测工具确认注入成功。你只有 {self.max_steps} 次尝试机会。
        
【工作流规范】
1. 仔细阅读【当前网络场景】和【故障参考文档】以及【任务】
2. 依次调用适当的工具，注入故障，注意参数需要从【当前网络场景】中获得，若用户指定参数则需要严格按照用户指示，若没有指定可以自己指定，无输出通常表示命令执行成功
3. 依次调用适当的工具，检测故障，注意参数需要从【当前网络场景】中获得
4. 结合工具的输出检查故障注入是否成功
5. 当确诊注入成功或彻底失败，必须立刻调用 `submit_inject` 工具提交三个核心参数。绝不可仅把答案写在文本中！

【注意事项】
- 得出最终的故障结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_inject` 工具，只有这样系统才能接收到你的答案！
- 切勿一次性调用大量不相关的工具，应按照逻辑链条一步一步注入并检测
- 所有工具输出结果都是稳定正确的，同样的工具+同样的输入参数切勿调用两次以上！
"""
        return SYSTEM_PROMPT

    async def inject_check_fault(self, timeout: int = 1200) -> Dict[str, Any]:
        print(f"\n[InjectAgent] 🚀 启动注入流程...")
        self.system_prompt = await self._get_system_prompt()
        
        # 将提示词块合并打印
        init_log = (
            f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
            f"{self.system_prompt}\n"
            f"{'='*70}"
        )
        print(init_log)

        result_payload = {
            "inject_result": "unknown",
            "fault_description": "unknown",
            "expected_fault": "unknown",
            "expected_location": "unkown"
        }

        mcp_server_dir = os.path.join(src_dir, "mcp_server")
        custom_env = os.environ.copy()
        custom_env["LAB_NAME"] = self.lab_name 
        # ⚠️ 新增这一行：删掉终端提示符变量，还你一个干净清爽的控制台！
        custom_env.pop("PS1", None)

        connections = {}
        server_path = os.path.join(mcp_server_dir, "klonet_server.py")
        if os.path.exists(server_path):
            connections["klonet_server"] = {"command": sys.executable, 
                                            "args": [server_path],
                                            "transport": "stdio", 
                                            "env": custom_env}

        client = MultiServerMCPClient(connections)

        try:
            server_tools = await client.get_tools()
            tools = [submit_inject] + server_tools
            agent_executor = create_agent(model=self.llm, tools=tools)

            inputs = {"messages": [SystemMessage(content=self.system_prompt), HumanMessage(content=f"请帮我注入：{self.fault_query}")]}
            config = {"recursion_limit": self.max_steps}

            async def _process_stream():
                async for chunk in agent_executor.astream(inputs, config=config, stream_mode="values"):
                    last_msg = chunk["messages"][-1]
                    if last_msg.type == "ai":
                        if last_msg.content:
                            print(f"\n🤔 [Thought]: {last_msg.content.strip()}")
                        # 核心解析：精准捕获大模型传出的三个变量
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                print(f"\n🛠️ [Action]: Call '{tc['name']}' with {tc['args']}")
                                if tc['name'] == 'submit_inject':
                                    result_payload["inject_result"] = tc['args'].get("result", "fatal")
                                    result_payload["fault_description"] = tc['args'].get("fault_description", "")
                                    result_payload["expected_fault"] = tc['args'].get("expected_fault", "")
                                    result_payload["expected_location"] = tc['args'].get("expected_location", "")

                    # 记录 Tool 的 Observation
                    elif last_msg.type == "tool":
                        t_name = last_msg.name
                        raw_content = last_msg.content
                        clean_text = str(raw_content)

                        if isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict):
                            clean_text = raw_content[0].get('text', str(raw_content))
                        clean_text = clean_text.strip()

                        if "submit" in t_name:
                            log_str = f"\n📕 [Submission]: {clean_text}"
                            print(log_str)
                        else:
                            log_str = f"\n👁️ [Observation from {t_name}]: {clean_text}"
                            print(log_str)
            
            await asyncio.wait_for(_process_stream(), timeout=timeout)

        except asyncio.TimeoutError:
            print(f"⚠️ [Agent 中断]: 诊断流程执行超时 ({timeout} 秒)！")
        except GraphRecursionError:
            print(f"⚠️ [Error]: Reached max steps limit.")
        except Exception as e:
            print(f"【详细错误追踪】:\n{traceback.format_exc()}")

        return result_payload
    
async def run_inject_agent_node(state: InjectState):
    # 包装为节点
    agent = FaultInjectAgent(
        lab_name=state["lab_name"],
        max_steps=state["max_steps"],
        netenv_info=state["netenv_info"],
        fault_query=state["fault_query"],
        backend_model=state["actor_model"]
    )
    res = await agent.inject_check_fault()
    return {
        "inject_result": res.get("inject_result", "fatal"),
        "problem_info": res.get("fault_description", "未知现象"),
        "expected_fault": res.get("expected_fault", "unknown_fault"),
        "expected_location": res.get("expected_location", "unknown_location")
    }

# ==========================================
# 4. 构建子图
# ==========================================
def build_inject_graph():
    workflow = StateGraph(InjectState)
    workflow.add_node("run_inject", run_inject_agent_node)
    workflow.add_edge(START, "run_inject")
    workflow.add_edge("run_inject", END)
    return workflow.compile()