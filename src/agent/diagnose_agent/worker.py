import asyncio
import time, json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from utils.llm_models import load_model
from .state import WorkerState, WorkerResult
from .tools import create_worker_tools

async def worker_think_node(state: WorkerState):
    """
    【思考决策】
    Worker 为高并发节点，统一调度，保证速度。
    """
    tools = await create_worker_tools(state["lab_name"])
    llm = load_model(backend_model="qwen3.5-medium").bind_tools(tools)

    if not state["messages"]:
        sys_prompt = f"""你是一名网络排障专家，严格依照下方资料，验证网络中是否存在指派的故障。
【网络拓扑】
{state['netenv_info']}

【全局巡检结果】
{state['inspector_result']}

【知识背景】
{state['knowledge_bg']}

【成功经验】
{state['success_exp']}

【负责排查】
{state['target_fault']}     

【网络参数说明】
- host_name/node: 节点名（如 'h1', 'server'）
- link: 链路名（如 'l1', 'l8'），注意不是网卡名
- iface: 网卡接口名（如 'tor1_1', 'tos1_1'），以 'to' 开头
- command: 包含参数的完整命令（如 'ping -c 5 192.168.1.22'）

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

【工作流要求】
1. 结合信息，直接开始调用命令验证。迷惑时可使用 smart_mentor_tool() 工具
2. 一次调用一个工具，得到结果思考后再操作，遵循 Think -> Act -> Observe 流程(React)
3. 当你认为已经诊断出假设中的故障或者确认没有故障时，必须调用 submit_diagnosis() 工具提交并结束

【提交答案规范】
当你验证完毕后，必须调用 submit_diagnosis()。参数必须是合法的 JSON 字符串，格式如下：
{{
    "existing": true/false,
    "location": ["节点名1", "节点名2"], // 如果 existing 为 false，此处留空数组 []
    "reason": "你发现的关键证据或正常现象的简短总结"
}}
绝对不允许提交其他未分配给你排查的故障！如果没发现，务必提交 existing 为 false。

【铁律规范 - 违者直接判负】
1. 严禁空谈: 必须调用工具，严禁只输出纯文本分析！
2. 严禁死循环: 绝对禁止连续执行完全一样的命令！
3. 果断结束: 如果按照知识背景查了关键节点发现正常，必须立刻调用 `submit_diagnosis` (existing: false) 结束任务！不要盲目乱猜！
4. 绝对禁止执行修改类命令: 严禁使用 add, del, set, flush, clear 等改变网络状态的命令！你的任务是诊断，不是修复！
5. 拓扑中只存在【网络拓扑】中明确列出的节点。绝对不允许猜测、凭空捏造并访问 h13、h99 等不存在的主机！
6. 强制批处理: 如果你想检查多台主机的路由或网卡，必须且只能使用批处理工具，违者强制拦截！
7. 保持语言简洁，不要重复生成已知的背景信息
"""

        # 👇 【核心修复 4：透明打印，让你看到 RAG 是否成功】
        print(f"\n" + "-"*50)
        print(f"🕵️ [{state['worker_id']}] 唤醒！排查目标: {state['target_fault']}")
        print(f"📖 注入知识库: {state.get('knowledge_bg', '')} 字符")
        print(f"🎓 注入导师经验: {state.get('success_exp', '无')}...")
        print("-" * 50)

        # 严格分离 SystemMessage (赋予人设与规则) 和 HumanMessage (发出具体的查询动作)
        # 这能完美通过 Qwen multi_step_tool 的 Jinja 模板校验
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"开始针对你的负责领域排查")
        ]
    else:
        messages = list(state["messages"])
        
    response = await llm.ainvoke(messages)
    
    usage = dict(state["token_usage"])
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage["input_tokens"] += response.usage_metadata.get("input_tokens", 0)
        usage["output_tokens"] += response.usage_metadata.get("output_tokens", 0)
        usage["total_tokens"] += response.usage_metadata.get("total_tokens", 0)

    return {"messages": [response], "token_usage": usage}

async def worker_tool_filter_node(state: WorkerState):
    """
    【工具执行和过滤】
    执行工具并自动摘要防溢出。
    """
    # --- 提取 LLM 输出的工具信息 ---
    last_msg = state["messages"][-1]

    # 大模型如果产生了“纯文本幻觉”没调工具，必须强行打回警告！
    if not hasattr(last_msg, 'tool_calls') or not last_msg.tool_calls:
        print(f"⚠️ [{state['worker_id']}] 产生纯文本幻觉，未调用工具！")
        warn_msg = HumanMessage(content="【系统严重警告】你刚才回复了纯文本分析，这是不允许的！你必须调用具体诊断工具，或者调用 `submit_diagnosis` 结束任务！绝不允许反复思考不行动。")
        return {"messages": [warn_msg]}
    
    # 👇 【核心修复 5：动态记忆裁剪与防沉迷系统】
    # 计算当前对话轮数，如果超过 10 轮，大模型大概率已经傻了，直接帮它强制提交！
    if len(state["messages"]) > 10:
        print(f"🛑 [{state['worker_id']}] 对话过长可能导致幻觉，系统强制切断并判负！")
        return {
            "has_submitted": True, 
            "submitted_result": {"existing": False, "location": [], "reason": "排查过程过长且无进展，系统强制判断为无此故障。"}
        }

    tools = await create_worker_tools(state["lab_name"])
    tool_map = {t.name: t for t in tools}
    
    results = []
    tool_count = state["tool_call_count"]
    has_sub = state["has_submitted"]
    
    sub_result = state.get("submitted_result", {}) 
    usage = dict(state["token_usage"])
    
    # 提取历史所有执行过的命令，构建“防重复记忆池”
    past_cmds = set()
    for msg in state["messages"][:-1]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                cmd = tc.get("args", {}).get("cli_cmd", "") or tc.get("args", {}).get("command", "")
                if cmd: past_cmds.add(cmd.strip())

    MAX_CONCURRENT_TOOLS = 20
    to_process = last_msg.tool_calls[:MAX_CONCURRENT_TOOLS]
    ignored = last_msg.tool_calls[MAX_CONCURRENT_TOOLS:]

    # --- 执行工具并过滤 ---
    async def process_single_tool(tc):
        # 执行工具
        t_name = tc["name"]
        t_args = tc["args"]
        
        # 1：拦截 LLM 的 XML 溢出格式
        has_garbage = False
        for k, v in t_args.items():
            if isinstance(v, str) and ("<tool_call>" in v or "<parameter=" in v or "</" in v or "<function=" in v):
                has_garbage = True
                break
        if has_garbage:
            print(f"⚠️ [{state['worker_id']}] 发现脏数据，已要求 Agent 纠正格式。")
            return "garbage", ToolMessage(tool_call_id=tc["id"], name=t_name, content="【系统拒绝】你的参数格式出错！请严格输出干净的参数字符串，不要包含XML标签或思考过程！"), {}

        print(f"🔧 [{state['worker_id']}] 执行: {t_name} | 参数: {t_args}")

        # 重复指令物理拦截
        if t_name in ["node_execute", "multi_node_execute"]:
            cmd = t_args.get("cli_cmd", "") or t_args.get("command", "")
            if cmd and cmd.strip() in past_cmds:
                print(f"🛑 [{state['worker_id']}] 拦截重复死循环命令: {cmd}")
                return "normal", ToolMessage(
                    tool_call_id=tc["id"], 
                    name=t_name, 
                    content=f"【系统物理拦截】你已经执行过完全相同的命令 '{cmd}'！严禁死循环！请思考现有线索，如果你确信找不到该故障，请立刻调用 submit_diagnosis (existing: false) 提交报告！"
                ), {}
            past_cmds.add(cmd.strip()) # 加入记忆池

        # 2. 处理提交工具
        if t_name == "submit_diagnosis":
            try:
                res = json.loads(t_args.get("faults_json_str", "{}"))
                print(f"🎯 [{state['worker_id']}] 确认状态: {res.get('existing', False)}")
            except Exception:
                res = {"existing": False, "location": [], "reason": "解析失败"}
            return "submit", ToolMessage(tool_call_id=tc["id"], name=t_name, content="提交成功。"), res
        
        # 3. 执行真实的底层网络工具
        t_func = tool_map.get(t_name)
        if not t_func:
            return "normal", ToolMessage(tool_call_id=tc["id"], name=t_name, content="[Error] 找不到该工具。"), {}

        try:
            raw_str = str(await t_func.ainvoke(t_args))
        except Exception as e:
            return "normal", ToolMessage(tool_call_id=tc["id"], name=t_name, content=f"[Error] 工具执行失败: {e}"), {}
        
        # 4. LLM 摘要调用
        final_content = f"[工具输出] {raw_str[6:992]}...\n" if len(raw_str) > 1000 else f"[工具输出] {raw_str}\n"
        tokens = {"in": 0, "out": 0}
        
        if len(raw_str) > 100: 
            llm = load_model(backend_model="qwen3.5-medium")
            prompt = f"""你的职责是总结提炼网络故障诊断 agent 调用工具的输出，防止上下文太长。
    【当前网络拓扑】
    {state["netenv_info"]}

    【用户投诉】
    {state["problem_info"]}

    【诊断假设】
    {state["target_fault"]}

    【调用工具】
    [工具] {t_name} | [参数] {t_args}

    【工具输出】
    {raw_str}

    请你提取包含 DOWN, error, fail, timeout, unreachable, Idle, shutdown 等等可能导致故障的异常信息的上下文(限300字) 并发表专家意见。
    若正常则回'无明显异常'。
    """ 
            try:
                summary_res = await llm.ainvoke([HumanMessage(content=prompt)])
                if hasattr(summary_res, 'usage_metadata') and summary_res.usage_metadata:
                    tokens["in"] = summary_res.usage_metadata.get("input_tokens", 0)
                    tokens["out"] = summary_res.usage_metadata.get("output_tokens", 0)
                    tokens["total"] = summary_res.usage_metadata.get("total_tokens", 0)
                final_content += f"[专家总结] {summary_res.content}"
            except Exception as e:
                final_content += "[专家总结异常] 查看原始输出。"
            
        return "normal", ToolMessage(tool_call_id=tc["id"], name=t_name, content=final_content), tokens
    
    tasks = [process_single_tool(tc) for tc in to_process]
    processed_results = await asyncio.gather(*tasks)

    # 结果回填聚合
    for _, (ret_type, tool_msg, extra) in enumerate(processed_results):
        results.append(tool_msg)
        if ret_type == "submit":
            has_sub = True
            sub_result = extra  # 此时无论进不进这里，顶部都已经安全初始化了 sub_result
        elif ret_type == "normal" and extra:
            usage["input_tokens"] += extra.get("in", 0)
            usage["output_tokens"] += extra.get("out", 0)
            usage["total_tokens"] += extra.get("total", 0)

    # 对超出的“无脑穷举工具”直接驳回打脸
    for tc in ignored:
        print(f"🛑 [{state['worker_id']}] 拦截超发穷举工具: {tc['name']}")
        results.append(ToolMessage(
            tool_call_id=tc["id"], 
            name=tc["name"], 
            content="【系统限制】单次操作工具数量上限为5个，此调用已被强行拦截！严禁无脑遍历查询所有节点！请先根据前5个工具的输出进行逻辑推理。"
        ))

    return {
        "messages": results,
        "tool_call_count": tool_count,
        "has_submitted": has_sub,
        "submitted_result": sub_result, # 修复 1 生效处
        "token_usage": usage
    }

# 【核心修复：强制兜底节点】
async def force_submit_node(state: WorkerState):
    """当思考步数过多时，系统强制判负并结束"""
    print(f"🛑 [{state['worker_id']}] 思考步数超限，陷入死循环，系统强行终止！")
    sub_res = {
        "existing": False, 
        "location": [], 
        "reason": "思考步数超过系统安全上限，可能陷入死循环，系统强制判定该故障排除。"
    }
    return {"has_submitted": True, "submitted_result": sub_res}

def should_continue_worker(state: WorkerState):
    if state.get("has_submitted", False):
        return "finalize_worker"
    
    # 如果 messages 对话轮数太多（比如超过 50 轮），强行斩断死循环！
    if len(state.get("messages", [])) >= 50:
        return "force_submit_node"
        
    return "worker_think_node"

async def finalize_worker(state: WorkerState):
    """构造纯净的 ReAct 轨迹，剔除冗长的系统提示词"""
    clean_trajectory = []
    for msg in state["messages"]:
        if isinstance(msg, AIMessage) and msg.content:
            clean_trajectory.append(f"[Thought]: {msg.content}")
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                clean_trajectory.append(f"[Action]: {tc['name']}({tc['args']})")
        if isinstance(msg, ToolMessage):
            clean_trajectory.append(f"[Observation]: {msg.content}") 
            
    traj_str = "\n".join(clean_trajectory)

    # 解析 worker 最终提交的结果字典
    sub_res = state.get("submitted_result", {})

    result = WorkerResult(
        worker_id=state["worker_id"],
        target_fault=state["target_fault"],          # 【修复】对齐新键名
        existing=sub_res.get("existing", False),     # 【新增】拆解新结构
        location=sub_res.get("location", []),        # 【新增】拆解新结构
        reason=sub_res.get("reason", ""),            # 【新增】拆解新结构
        trajectory_log=traj_str,
        execution_time=time.time() - state["start_time"],
        token_usage=state["token_usage"],
        tool_call_count=state["tool_call_count"]
    )
    return {"worker_results": [result]}

# --- 组装 Worker 图 ---
worker_workflow = StateGraph(WorkerState)
worker_workflow.add_node("worker_think_node", worker_think_node)
worker_workflow.add_node("worker_tool_filter_node", worker_tool_filter_node)
worker_workflow.add_node("force_submit_node", force_submit_node) # 新增
worker_workflow.add_node("finalize_worker", finalize_worker)

worker_workflow.add_edge(START, "worker_think_node")
worker_workflow.add_edge("worker_think_node", "worker_tool_filter_node")

# 修改路由边，加入 force_submit_node
worker_workflow.add_conditional_edges(
    "worker_tool_filter_node", 
    should_continue_worker, 
    {
        "finalize_worker": "finalize_worker", 
        "worker_think_node": "worker_think_node",
        "force_submit_node": "force_submit_node"  # 步数超限时走向这里
    }
)

worker_workflow.add_edge("force_submit_node", "finalize_worker") # 强行结束进入结算
worker_workflow.add_edge("finalize_worker", END)
worker_graph = worker_workflow.compile()