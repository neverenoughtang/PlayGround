# src/agent/diagnose_agent/worker.py
import time
import asyncio
from typing import Annotated, TypedDict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent

from utils.llm_models import load_model
from utils.diagnose_worker_sql import DiagnoseWorkerKnowledgeBase
from .tools import create_worker_tools
from .state import WorkerState, WorkerResult 

async def worker_react_node(state: WorkerState):
    """
    【流式异步 Worker 核心引擎】
    摒弃了以前冗长的历史遍历。采用原生的 create_agent 机制，
    通过 astream(stream_mode="values") 单次流式监听，实时抓取推理轨迹，计算资源账单。
    """
    # 1. 初始化基础变量
    start_time = time.perf_counter()
    worker_id = state.get("worker_id", "Worker-X")
    target_fault = state.get("target_fault", "unknown_fault")

    print(f"🕵️ [{worker_id}] 启动排查任务 | 目标: {target_fault}")

    # 2. 动态挂载 MySQL 专属诊断知识
    kb = DiagnoseWorkerKnowledgeBase()
    knowledge_text = await kb.query_fault_knowledge(target_fault)
    if not knowledge_text:
        knowledge_text = "⚠️ 未查找到该故障的专属指南，请基于通用网络知识进行诊断。"

    print(f"📖 [{worker_id}] 成功挂载数据库知识: 约 {len(knowledge_text)} 字符")

    # 3. 组装极具压迫感的系统提示词 (System Prompt)
    sys_prompt = f"""你是一线网络排障专家。你当前唯一的任务是验证网络中是否存在故障：【{target_fault}】
【网络拓扑信息】
{state["netenv_info"]}

【用户投诉表象】
{state.get('target_symptom', '未知')}

【专属诊断知识字典】
{knowledge_text}
必须严格遵照此步骤排查！

【全局巡检结果】
{state.get('inspector_result', '')}

【平台指令规范】
- 绝对禁止
1. 输出重定向符: `>` `>>`
错误: `echo "config" > /etc/file.conf`
正确: 不要在命令行中写文件
2. 逻辑拼接符: `&&` `||`
错误: `pkill zebra && pkill bgpd`
正确: 分两次调用 `node_execute`
3. 管道符: `|`
错误: `ps aux | grep zebra`
正确: 执行 `ps aux` 后用 Python 或 LLM 自己提取
4. 命令替换: `` `command` `` 或 `$(command)`
错误: `kill -9 $(pidof zebra)`
正确: 直接用 `pkill zebra`
5. 单引号陷阱（复杂传参时）
错误: `vtysh -c 'router bgp 65000'`
正确: `vtysh -c "router bgp 65000"`
- 化繁为简: 一个动作需要 3 步，必须调用 3 次工具
- 所见即所得: 不要在命令行中做逻辑判断（if/for 循环）
- 只读不写: 尽量避免动态向容器内写入脚本 

【铁律规范 - 违者直接判负】
1. 严禁单节点遍历：多个节点处理一条指令调用 `multi_node_execute`，多节点处理多个指令调用 `batch_execute`！
2. 禁止使用以下指令： 
    - ping
    - ip neigh
    - ip -br link 
    - vtysh -c "show ip bgp summary" 2>/dev/null
    - vtysh -c "show ip ospf neighbor" 2>/dev/null
    - vtysh -c "show ip rip status" 2>/dev/null
    这些内容已经包含在【全局巡检结果】中，不要重复探测一样的东西！
2. 发现没有你负责的故障也很正常，这时请相信自己，直接提交！
3. 系统限制你最多只能调用 20 次工具，请精打细算！
4. 当你确信发现证据，或排查完关键节点确认无故障时，【必须且只能】调用 `submit_diagnosis` 工具结束任务！
5. 语言一定要简洁，不要啰嗦！
"""

    # 4. 初始化工具与大模型
    tools = await create_worker_tools(state["lab_name"])
    # 过滤掉不需要的旧版工具
    tools = [t for t in tools if t.name != "smart_mentor_tool"] 
    llm = load_model(backend_model="qwen3.6-medium")
    
    # 构建智能体执行器
    agent_executor = create_agent(llm, tools, system_prompt=sys_prompt)
    inputs = {"messages": [HumanMessage(content=f"请开始针对 {target_fault} 展开排查。")]}

    # ---------------------------------------------------------
    # 5. 状态追踪器初始化
    # ---------------------------------------------------------
    tool_call_count = 0
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    trajectory_log = []       # 记录所有的思考、动作、观察，用于最终输出
    
    is_existing = False       # 是否发现故障
    fault_location = []       # 故障节点列表
    fault_reason = ""         # 判定理由
    called_submit = False     # 是否主动调用了 submit_diagnosis
    stop_reason = "normal"    # 退出原因标识
    processed_msg_ids = set() # 记录已处理的消息 ID，防止重复打印

    # ---------------------------------------------------------
    # 6. 流式监听核心协程 (内联函数)
    # ---------------------------------------------------------
    async def _process_stream():
        nonlocal tool_call_count, is_existing, fault_location, fault_reason, called_submit, stop_reason
        
        # 限制大模型的递归深度，相当于限制它不断胡思乱想的次数
        async for chunk in agent_executor.astream(inputs, config={"recursion_limit": 42}, stream_mode="values"):
            last_msg = chunk["messages"][-1]
            msg_id = getattr(last_msg, "id", id(last_msg))

            # 避免流式输出中的重复处理
            if msg_id in processed_msg_ids:
                continue
            processed_msg_ids.add(msg_id)

            if isinstance(last_msg, HumanMessage):
                continue

            # 👉 [指标统计] 实时累加 Token
            if hasattr(last_msg, 'usage_metadata') and last_msg.usage_metadata:
                token_usage["input_tokens"] += last_msg.usage_metadata.get("input_tokens", 0)
                token_usage["output_tokens"] += last_msg.usage_metadata.get("output_tokens", 0)
                token_usage["total_tokens"] += last_msg.usage_metadata.get("total_tokens", 0)

            # 👉 [AI 行为捕获] 抓取思考(Thought)与动作(Action)
            if isinstance(last_msg, AIMessage):
                if last_msg.content:
                    log_str = f"🤔 [{worker_id}][Thought]: {last_msg.content.strip()}"
                    trajectory_log.append(log_str)
                    print(log_str)

                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    for tc in last_msg.tool_calls:
                        tool_call_count += 1
                        t_name, t_args = tc['name'], tc['args']
                        
                        log_str = f"🛠️ [{worker_id}][Action]: Call '{t_name}' with {t_args}"
                        trajectory_log.append(log_str)
                        print(log_str)

                        # 如果是提交动作，当场拦截解析参数
                        if t_name == "submit_diagnosis":
                            called_submit = True
                            
                            # 1. 强悍的布尔值解析 (防止大模型传字符串 "True" 或 "False")
                            raw_ex = t_args.get("existing", False)
                            if isinstance(raw_ex, str):
                                is_existing = raw_ex.lower() in ["true", "1", "yes", "y", "t"]
                            else:
                                is_existing = bool(raw_ex)
                            
                            # 2. 强悍的列表解析 (防止大模型传字符串 "['h1']")
                            raw_loc = t_args.get("location", [])
                            if isinstance(raw_loc, str):
                                try:
                                    import ast
                                    clean_loc = ast.literal_eval(raw_loc)
                                    fault_location = clean_loc if isinstance(clean_loc, list) else [raw_loc]
                                except:
                                    fault_location = [raw_loc] if raw_loc.strip() else []
                            else:
                                fault_location = list(raw_loc) if raw_loc else []
                                
                            fault_reason = str(t_args.get("reason", "提交了结论但未提供理由。"))
                            
                            log_str = f"📕 [{worker_id}][Submission]: 判定为 {is_existing} | 节点: {fault_location}"
                            trajectory_log.append(log_str)
                            print(log_str)

                        # 物理拦截：如果没提交却达到了工具调用上限
                        if tool_call_count >= 20 and not called_submit:
                            print(f"⚠️ [{worker_id}] 工具调用达上限 (20次)，强行打断工作流！")
                            stop_reason = "tool_limit"
                            raise Exception("TOOL_LIMIT_EXCEEDED")

            # 👉 [工具回显捕获] 抓取观察结果(Observation)
            elif isinstance(last_msg, ToolMessage):
                clean_text = str(last_msg.content).strip()
                # 如果回显太长，做一下物理截断保持控制台清爽
                if len(clean_text) > 300:
                    clean_text = clean_text[:300].replace('\n', ' ') + "... (内容过长已截断)"
                else:
                    clean_text = clean_text.replace('\n', ' ')
                
                log_str = f"👁️ [{worker_id}][Observation from {last_msg.name}]: \n{clean_text}"
                trajectory_log.append(log_str)
                print(log_str)

    # ---------------------------------------------------------
    # 7. 启动推理流并施加严格限时保护 (5分钟)
    # ---------------------------------------------------------
    try:
        await asyncio.wait_for(_process_stream(), timeout=300.0)
    except asyncio.TimeoutError:
        print(f"🛑 [{worker_id}] 执行超过 5 分钟，触发系统物理熔断！")
        stop_reason = "timeout"
    except Exception as e:
        if str(e) != "TOOL_LIMIT_EXCEEDED":
            print(f"🛑 [{worker_id}] 原生推理引擎异常中断: {e}")
            stop_reason = f"error: {e}"

    # ---------------------------------------------------------
    # 8. 智能兜底：如果笨模型一直没调提交工具，帮它体面收场
    # ---------------------------------------------------------
    if not called_submit and stop_reason != "error":
        print(f"⚠️ [{worker_id}] Agent 未主动提交答案，系统启动智能兜底！")
        is_existing = False
        fault_location = []
        fault_reason = f"系统强制兜底 (终止原因: {stop_reason})。未发现确凿证据。"
        # 倒序遍历日志，抓取它的最后一次 Thought 作为理由
        for log in reversed(trajectory_log):
            if "[Thought]" in log:
                fault_reason = f"系统兜底提取模型最后思维: {log}"
                break

    # ---------------------------------------------------------
    # 9. 封装返回结果
    # ---------------------------------------------------------
    exec_time = time.perf_counter() - start_time
    print(f"🎯 [{worker_id}] 排查收官! 结论: {is_existing} | 位置: {fault_location} | 耗时: {exec_time:.1f}s")
    print("="*70 + "\n")

    worker_res: WorkerResult = {
        "worker_id": worker_id,
        "target_fault": target_fault,
        "existing": is_existing,
        "location": fault_location,
        "reason": fault_reason,
        "trajectory_log": "\n".join(trajectory_log),
        "execution_time": exec_time,
        "tool_call_count": tool_call_count,
        "token_usage": token_usage
    }

    return {"worker_results": [worker_res]}

# ==========================================
# ⚙️ 构建与暴露极简 Worker 子图
# ==========================================
worker_workflow = StateGraph(WorkerState)
worker_workflow.add_node("worker_react_node", worker_react_node)
worker_workflow.add_edge(START, "worker_react_node")
worker_workflow.add_edge("worker_react_node", END)

# 暴露给图外层 run_worker_wrapper 去 ainvoke
worker_graph = worker_workflow.compile()