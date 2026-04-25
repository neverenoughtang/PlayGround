# src/agent/fault_inject_agent.py
import asyncio
import os 
import sys
import time
import json
import traceback
from typing import Dict, Any, Optional, TypedDict, List
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

from mcp_server.klonet_base_api import KlonetBaseAPI  
from utils.llm_models import load_model
from utils.fault_inject_rag import FaultKnowledgeBase

# ==========================================
# 1. 状态定义
# ==========================================
class InjectState(TypedDict):
    lab_name: str
    netenv_info: str
    fault_query: str      # 用户的原始诉求（可能包含多个复合故障）
    actor_model: str
    max_steps: int
    
    # 输出流转参数
    inject_result: str    # "successful" 或 "fatal"
    problem_info: str     # Agent 依据注入结果自己合成的【大白话用户投诉】
    expected_faults: Dict[str, List[str]] # 【格式变更】复合故障的 JSON 字典结果

# ==========================================
# 2. 全局缓存与自定义工具定义
# ==========================================
# 在类外部定义一个全局变量，作为 RAG 模型的缓存，避免多次注入任务重复加载权重
# 分别为 RAG、MCP Client 和 MCP 工具列表建立独立的全局缓存
_GLOBAL_INJECT_RAG_CACHE = None
# 【核心修复】：将单一变量改为字典，支持多拓扑实例共存
_INJECT_MCP_CLIENTS = {}
_INJECT_MCP_TOOLS_CACHE = {}

async def prewarm_inject_caches(lab_name: str):
    """
    【极速热启动】
    在系统启动时一次性加载 RAG 模型、向量库和 MCP 服务器。
    [1] 注入层维护自己独立的 MCP Client，防止与诊断层发生 stdio 通信抢占。
    [2] 以 lab_name 为键隔离 MCP Server，彻底解决跨拓扑测试的上下文污染。
    """
    global _GLOBAL_INJECT_RAG_CACHE, _INJECT_MCP_CLIENTS, _INJECT_MCP_TOOLS_CACHE
    print("🔥 [系统预热] 正在预热故障注入层 MCP 工具与 RAG 知识库缓存...")
    
    # 1. 预热 MCP 工具
    if lab_name not in _INJECT_MCP_TOOLS_CACHE:
        mcp_server_dir = os.path.join(src_dir, "mcp_server")
        custom_env = os.environ.copy()
        custom_env["LAB_NAME"] = lab_name
        custom_env.pop("PS1", None) # 消除终端提示符

        server_path = os.path.join(mcp_server_dir, "klonet_server.py")
        connections = {"klonet_server": {"command": sys.executable, "args": [server_path], "transport": "stdio", "env": custom_env}}
        
        client = MultiServerMCPClient(connections)
        _INJECT_MCP_CLIENTS[lab_name] = client
        _INJECT_MCP_TOOLS_CACHE[lab_name] = await client.get_tools()
        print(f"   ✅ 注入层 MCP ({lab_name}) 底层工具预加载完成")
        
    # 2. 预热 RAG 数据库 (底层会自动复用内存中的 HuggingFace 模型权重)
    if _GLOBAL_INJECT_RAG_CACHE is None:
        _GLOBAL_INJECT_RAG_CACHE = FaultKnowledgeBase(force_rebuild=False)
        print("   ✅ 注入层 RAG 向量数据库与 NLP 预加载完成")

# --- Linux TC 工具 (1个) ---
@tool()
def tc_set(
    host_name: str,
    link: str,
    bw_kbps: Optional[int] = None,
    delay_ms: Optional[int] = None,
    jitter_ms: Optional[int] = None,
    loss: Optional[int] = None,
) -> str:
    """
    在主机的指定链路上**设置**流量控制 (TC) 参数
    Args:
        host_name: 主机名称
        link: 链路名
        bw_kbps: 带宽限制(可选)
        delay_ms: 时延(ms, 可选)
        jitter_ms: 抖动(ms, 可选)
        loss: 丢包率(%, 可选)
        
    Returns:
        response (str): 包含端口监听状态和 Python 推理进程详情。
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab) 

    config = {
        "linkchoice": "static",
        "link": link,
        "ne": host_name
    }

    if bw_kbps is not None:
        config["bw_kbps"] = str(bw_kbps)
    if delay_ms is not None:
        config["delay_us"] = str(delay_ms * 1000)
    if jitter_ms is not None:
        config["jitter_us"] = str(jitter_ms * 1000)
    if loss is not None:
        config["loss"] = str(loss)

    return str(API.lab.configure_link(config=config))

@tool
def search_fault_manual(query: str, count: int = 2) -> str:
    """
    当你不清楚如何注入某种故障时，调用此工具搜索故障手册。
    Args:
        query: 故障的描述或关键词（例如 "BGP邻居断开"、"链路丢包"）。
        count: 需要返回的最佳匹配手册条数。默认返回 2 条。
    Returns:
        注入该故障所需的工具命令、参数和检测标准。
    """
    rag = _GLOBAL_INJECT_RAG_CACHE if _GLOBAL_INJECT_RAG_CACHE else FaultKnowledgeBase(force_rebuild=False)
    # Agent 传入的 query 可能是单个短语，动态设置 final_k
    return rag.search(query, ensemble_k=4*count, final_k=count)

@tool
def submit_inject(result: str, synthesized_problem_info: str, expected_faults_json: str) -> str:
    """
    当且仅当确认【所有】故障都已注入完成（或确认彻底失败）时调用。必须且只能调用一次。
    Args:
        result: 注入结果 (成功填 "successful"，失败填 "fatal")
        synthesized_problem_info: 综合所有成功注入的故障，编写一句含糊的“用户投诉信息”(如: "某主机跨域通信不通，且某主机通信延迟很高")。
        expected_faults_json: 注入成功的故障和对应节点的 JSON 字典字符串。必须严格遵循格式：'{"link_loss": ["h1", "h3"], "bgp_neighbor_shutdown": ["r1"]}'
    """
    return "提交成功，任务结束..."

# ==========================================
# 3. 智能体节点逻辑 (Nodes)
# ==========================================
class FaultInjectAgent:
    """
    故障注入智能体（Agentic RAG 版本）
    """
    def __init__(self, lab_name: str, max_steps: int, netenv_info: str, fault_query: str, backend_model: str = "qwen3.6-medium"):
        self.lab_name = lab_name  
        self.max_steps = max_steps
        self.netenv_info = netenv_info
        self.fault_query = fault_query
        self.llm = load_model(backend_model=backend_model)
        self.system_prompt = self._get_system_prompt() # 直接同步获取即可，不再依赖外部初始化

    def _get_system_prompt(self) -> str:
        # 【架构升级】移除硬编码填入的 problem_doc，转而教导 Agent 使用自主检索！
        SYSTEM_PROMPT = f"""你是一名专业的网络工程师，负责在仿真网络环境中注入复合故障，以便学生学习网络故障诊断。

【当前网络场景】
{self.netenv_info}

【网络参数说明】
- host_name/node: 节点名，如 'h1', 'server'
- link: 链路名，不是网卡名字! 如 'l1', 'l8'，**工具 `tc_set()` 中的参数 'link' 一定是链路名！**
- iface: 网卡(接口)名，字符串 'to' 开头，如 'to_s1_1'
- command: 包含参数的指令，如 'ping -c 5 192.168.1.22'

【任务】
用户需求: {self.fault_query}
依据用户需求，完成所有故障的注入。你有 {self.max_steps} 次操作机会。
        
【工作流规范（Agentic RAG）】
1. 分析用户需求：判断用户需要注入**几种**不同类型的故障。
2. 自主学习：针对其中一种故障，调用 `search_fault_manual` 工具查询注入它的规范和检测方法。
3. 注入与检测：根据手册中的说明，调用适当的 MCP 节点工具注入该故障，并使用相应的命令进行检测，确诊注入成功。
4. 迭代循环：如果还有其他的故障类型未注入，重复步骤 2 和 3，直到所有要求都被成功注入。
5. 综合总结：梳理所有成功注入的故障，结合手册中的“故障表现描述”，自己总结出一句通顺但含糊的自然语言作为大白话的【用户投诉信息】（比如："客户投诉某些主机完全失联，且出现延迟异常"）。
6. 最终提交：调用 `submit_inject` 结束任务。

【klonet指令规范】
## 绝对禁止使用的字符与语法
1. **输出重定向符：`>` 和 `>>`**
- 错误示范：`echo "config" > /etc/file.conf`
- 灾难后果：文件不会被创建，文本和 `>` 会被原样打印到屏幕控制台。
- 替代方案：不要在命令行中写文件。如果必须清空文件，使用 `cp /dev/null /etc/file.conf`。
2. **逻辑拼接符：`&&` 和 `||`**
- 错误示范：`pkill zebra && pkill bgpd`
- 灾难后果：执行器往往只能识别第一条命令，后面的命令被直接丢弃或报错。
- 替代方案：拆分为多次独立的 `node_execute` API 调用。
```python
node_execute("r1", "pkill zebra")
node_execute("r1", "pkill bgpd")
```
3. **管道过滤符：`|`** 
- 错误示范：`ps -ef | grep zebra` 或 `ping -c 4 10.0.0.1 | awk '{{print $1}}'`
- 灾难后果：无法解析管道，直接报 `grep: command not found` 或语法错误。
- 替代方案：执行全量输出命令（如 `ps aux` 或 `ping`），将完整结果返回后，利用 Python 代码或 LLM 本身的思考能力提取所需信息。
4. **命令替换符：`` ` ` `` (反引号) 和 `$()`**
- 错误示范：`kill -9 $(pidof zebra)`
- 灾难后果：变量不会在容器内被展开，导致命令失效。
- 替代方案：直接使用自带进程管理工具如 `pkill zebra`。
3. **单引号陷阱：`'...'` (在复杂传参时)**
- 错误示范：`vtysh -c 'router bgp 65000'`
- 灾难后果：JSON 序列化或底层 C/Go 接口传递时可能丢失转义，导致报错。
- 替代方案：统一使用标准的双引号包裹参数 `vtysh -c "router bgp 65000"`。
# 最佳实践原则
- 如果一个动作需要 3 步，必须调用 3 次 `node_execute` 工具，绝不毕其功于一役。
- 不要在命令行中做逻辑判断（如 `if`、`for` 循环），将逻辑运算拉回 Agent 自身的大脑或上层 Python 脚本中完成。
- 尽量避免动态向容器内写入新脚本，必须写入时，请由底层 Python 框架在拓扑启动阶段一次性完成加载。

【注意事项】
- 得出最终的结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_inject` 提交 JSON。
- 提交的 JSON 字典中，键(Key)必须是手册中规定的英文 `期待故障` 名称，值(Value)是被注入该故障的节点列表。
- 切勿一次性调用大量不相关的工具，应按照逻辑链条“查询手册 -> 注入 A -> 验证 A -> 查询手册 -> 注入 B -> 验证 B”分布执行。
"""
        return SYSTEM_PROMPT

    async def inject_check_fault(self, timeout: int = 1200) -> Dict[str, Any]:
        print(f"\n[InjectAgent] 🚀 启动多模态复合故障注入流程...")
        
        # 将提示词块合并打印
        init_log = (
            f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            f"┃ 📜 [System Prompt / 故障注入智能体记忆初始化]                         ┃\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
            f"{self.system_prompt}\n"
            f"{'='*70}"
        )
        print(init_log)

        # 初始化输出载体
        result_payload = {
            "inject_result": "unknown",
            "problem_info": "未检测到异常表现",
            "expected_faults": {}
        }

        try:
            # 1. 确保缓存已经预热 (通常 main.py 已经执行过)，使用当前实例的 self.lab_name 调取对应的缓存
            if self.lab_name not in _INJECT_MCP_TOOLS_CACHE or _GLOBAL_INJECT_RAG_CACHE is None:
                await prewarm_inject_caches(self.lab_name)
            
            # 2. 直接使用全局缓存的 MCP 工具，不再在每次运行时重复拉起 Server！
            tools = [submit_inject, search_fault_manual, tc_set] + _INJECT_MCP_TOOLS_CACHE[self.lab_name]
            
            # 3. 构建执行图
            agent_executor = create_agent(model=self.llm, tools=tools)
            inputs = {"messages": [SystemMessage(content=self.system_prompt), HumanMessage(content=self.fault_query)]}
            config = {"recursion_limit": self.max_steps}

            async def _process_stream():
                async for chunk in agent_executor.astream(inputs, config=config, stream_mode="values"):
                    last_msg = chunk["messages"][-1]
                    if last_msg.type == "ai":
                        if last_msg.content:
                            print(f"\n🤔 [Thought]: {last_msg.content.strip()}")
                        
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                print(f"\n🛠️ [Action]: Call '{tc['name']}' with {tc['args']}")
                                
                                # 核心解析：捕获结束信号和答案
                                if tc['name'] == 'submit_inject':
                                    result_payload["inject_result"] = tc['args'].get("result", "fatal")
                                    result_payload["problem_info"] = tc['args'].get("synthesized_problem_info", "无明显异常描述")
                                    
                                    # 安全解析大模型输出的 JSON 字典
                                    json_str = tc['args'].get("expected_faults_json", "{}")
                                    try:
                                        parsed_dict = json.loads(json_str)
                                        result_payload["expected_faults"] = parsed_dict
                                    except Exception as e:
                                        print(f"⚠️ [Error]: Agent 提交的字典 JSON 格式不合法 -> {e}")
                                        result_payload["expected_faults"] = {}

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
                        elif "search_fault_manual" in t_name:
                            # 为防止手册内容刷屏，在控制台可以做一定省略截断
                            print(f"\n📚 [RAG 检索结果]: 获取到 {len(clean_text)} 字符的参考资料。")
                        else:
                            log_str = f"\n👁️ [Observation from {t_name}]: {clean_text}"
                            print(log_str)
            
            # 使用带超时的执行闭包
            await asyncio.wait_for(_process_stream(), timeout=timeout)

        except asyncio.TimeoutError:
            print(f"⚠️ [Agent 中断]: 流程执行超时 ({timeout} 秒)！")
        except GraphRecursionError:
            print(f"⚠️ [Error]: Reached max steps limit.")
        except Exception as e:
            print(f"【详细错误追踪】:\n{traceback.format_exc()}")
        finally:
            # MCP server 会自动释放资源
            pass

        return result_payload
    
async def run_inject_agent_node(state: InjectState):
    # 包装为可嵌入图的节点
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
        "problem_info": res.get("problem_info", "未知现象"),
        "expected_faults": res.get("expected_faults", {}) # 输出统一为字典格式
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