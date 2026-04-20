import time, json
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from utils.llm_models import load_model
from .state import WorkerState, WorkerResult
from .tools import create_worker_tools

async def worker_think_node(state: WorkerState):
    """
    Worker 思考决策节点。
    【重要配置】Worker 为高并发节点，统一调度 qwen3.5-small，保证速度。
    """
    tools = await create_worker_tools(state["lab_name"])
    llm = load_model(backend_model="qwen3.5-small").bind_tools(tools)
    
    if not state["messages"]:
        sys_prompt = f"""你是一名网络排障专家。当前网络拓朴中的多个节点可能存在多种故障。
【网络拓扑】
{state['netenv_info']}

【用户投诉】
{state['problem_info']}

【全局巡检结果】
{state['inspector_result']}

【负责排查】
{state['hypothesis']}     

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
1. 结合信息，直接开始调用命令验证。迷惑时可使用 smart_mentor_tool() 工具。
2. 一次调用一个工具，得到结果思考后再操作，遵循 Think -> Act -> Observe 流程(React)，逐步缩小故障范围。
3. 当诊断出**假设中的**一条故障时，先记着这一条，重复 React 流程诊断假设内的其他故障。
4. 当你认为已经诊断出假设中全部故障或者确认没有故障时，必须调用 submit_diagnosis() 工具提交并结束。

【提交答案规范】
梳理出所有故障名，以及发生该故障的全部节点名称，传入严格 JSON。如果**你发现没有你诊断假设之内的故障，你可以提交空值**。
格式为 '{{<fault_1>: [fault_1_node_1, fault_1_node_2, ...], <fault_2>: [fault_2_node_1, fault_2_node_2...], ...}}'
例如：'{{"link_loss": ["h1", "h3"], "frr_service_down": ["r2"]}}'

【注意事项】
- 你只能诊断【负责排查】的内容，不准诊断提交其他的故障
- 有可能环境中不存在任何属于【负责排查】的故障，此时你应该提交空值
- 切勿一次性调用大量不相关工具，应按逻辑链条逐步推进
- 优先使用非破坏性观察类命令（show/dump/tc qdisc show/ip addr/vtysh show 等）
- 同样的工具+参数不要调用两次以上
- 请保持语言简洁，不要重复生成已知的背景信息。如果已经有嫌疑范围，请立即调用工具进行验证
"""
        # 👇 【核心修复】
        # 严格分离 SystemMessage (赋予人设与规则) 和 HumanMessage (发出具体的查询动作)
        # 这能完美通过 Qwen multi_step_tool 的 Jinja 模板校验
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=f"开始针对你的负责领域排查。")
        ]
    else:
        messages = list(state["messages"])
        
    response = await llm.ainvoke(messages)
    
    usage = dict(state["token_usage"])
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage["input_tokens"] += response.usage_metadata.get("input_tokens", 0)
        usage["output_tokens"] += response.usage_metadata.get("output_tokens", 0)
    
    return {"messages": [response], "token_usage": usage}

async def worker_tool_filter_node(state: WorkerState):
    """执行工具并自动摘要防溢出"""
    # 1. 提取 LLM 输出的工具信息
    last_msg = state["messages"][-1]
    if not (hasattr(last_msg, 'tool_calls') and last_msg.tool_calls):
        return {}

    tools = await create_worker_tools(state["lab_name"])
    tool_map = {t.name: t for t in tools}
    
    results = []
    tool_count = state["tool_call_count"]
    has_sub = state["has_submitted"]
    sub_faults = state["submitted_faults"]
    usage = dict(state["token_usage"])
    
    # 2. 逐条调用工具，并总结工具输出
    for tc in last_msg.tool_calls:
        # 执行工具
        tool_count += 1
        t_name = tc["name"]
        t_args = tc["args"]
        print(f"🔧 [{state['worker_id']}] 执行: {t_name} | 参数: {t_args}")
        
        if t_name == "submit_diagnosis":
            has_sub = True
            try:
                sub_faults = json.loads(t_args.get("faults_json_str", "{}"))
                print(f"🎯 [{state['worker_id']}] 确诊故障: {sub_faults}")
            except Exception:
                sub_faults = {}
            results.append(ToolMessage(tool_call_id=tc["id"], name=t_name, content="提交成功。"))
            continue

        t_func = tool_map.get(t_name)
        try:
            raw_str = str(await t_func.ainvoke(t_args))
        except Exception as e:
            results.append(ToolMessage(tool_call_id=tc["id"], name=t_name, content=f"[Error] {e}"))
            continue
        
        # LLM 专家总结要点
        final_content = ""
        if len(raw_str) > 2000:
            final_content = f"[工具输出] {raw_str[:1998]}...\n"
        else:
            final_content = f"[工具输出] {raw_str}\n"

        llm = load_model(backend_model="qwen3.5-small")
        prompt = f"""你的职责是总结提炼网络故障诊断 agent 调用工具的输出，防止上下文太长。
【当前网络拓扑】
{state["netenv_info"]}

【用户投诉】
{state["problem_info"]}

【诊断假设】
{state["hypothesis"]}

【调用工具】
[工具] {t_name} | [参数] {t_args}

【工具输出】
{raw_str}

请你提取包含 DOWN, error, fail, timeout, unreachable, Idle, shutdown 等等可能导致故障的异常信息的上下文(限300字) 并发表专家意见。
若正常则回'无明显异常'。

示例一：
    【当前网络拓扑】
     simple_bgp 的拓扑信息:

    [节点列表]
    - h1 [host] | 接口: tor1_1(192.168.2.2/24) | 默认网关: 192.168.2.1
    - h2 [host] | 接口: tor2_1(192.168.3.2/24) | 默认网关: 192.168.3.1
    - h3 [host] | 接口: tor2_1(192.168.4.2/24) | 默认网关: 192.168.4.1
    - h4 [host] | 接口: tor3_1(192.168.5.2/24) | 默认网关: 192.168.5.1
    - r1 [router] | 接口: tor2_1(192.168.0.1/24), toh1_1(192.168.2.1/24)
    - r2 [router] | 接口: tor1_1(192.168.0.2/24), toh2_1(192.168.3.1/24), toh3_1(192.168.4.1/24), tor3_1(192.168.1.1/24)
    - r3 [router] | 接口: toh4_1(192.168.5.1/24), tor2_1(192.168.1.2/24)

    [链路]
    - 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
    - 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
    - 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
    - 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
    - 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
    - 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

    【用户投诉】
    主机 h1 ping 不通 h3。

    【全局巡检结果】
    [略]

    【调用工具】
    [工具] check_bgp_status | [参数] 'router': 'r1'

    【工具输出】
    BGP router identifier 192.168.2.1, local AS number 65001
    RIB entries 3, using 336 bytes of memory
    Peers 1, using 9088 bytes of memory

    Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
    192.168.0.2     4 65002      11      12        0    0    0 00:00:53 Idle (Admin)

    Total number of neighbors 1

    Total num. Established sessions 0
    Total num. of routes received     0

    【BGP Config】:
    Building configuration...

    Current configuration:
    !
    hostname Router
    log stdout
    !
    password zebra
    enable password zebra
    !
    interface eth0
    !
    interface lo
    !
    interface toh1_1
    !
    interface tor2_1
    !
    interface tunl0
    !
    router bgp 65001
    bgp router-id 192.168.2.1
    network 192.168.0.0/24
    network 192.168.2.0/24
    redistribute connected
    timers bgp 5 15
    neighbor 192.168.0.2 remote-as 65002
    neighbor 192.168.0.2 shutdown
    neighbor 192.168.0.2 next-hop-self
    !
    address-family ipv6
    exit-address-family
    exit
    !
    ip forwarding
    !
    line vty
    !
    end

你应该输出：
    r1 与邻居 192.168.0.2（r2）的 BGP 会话状态是 "Idle (Admin)"，表示被管理员手动关闭了，BGP 配置中明确有 `neighbor 192.168.0.2 shutdown` 命令，导致 BGP 邻居关系无法建立。
"""
        summary_res = await llm.ainvoke([HumanMessage(content=prompt)])
        if hasattr(summary_res, 'usage_metadata') and summary_res.usage_metadata:
            usage["input_tokens"] += summary_res.usage_metadata.get("input_tokens", 0)
            usage["output_tokens"] += summary_res.usage_metadata.get("output_tokens", 0)
        final_content += f"[专家总结] {summary_res.content}"
       
        results.append(ToolMessage(tool_call_id=tc["id"], name=t_name, content=final_content))

    return {
        "messages": results,
        "tool_call_count": tool_count,
        "has_submitted": has_sub,
        "submitted_faults": sub_faults,
        "token_usage": usage
    }

def worker_should_continue(state: WorkerState):
    if state["has_submitted"] or time.time() - state["start_time"] > state["time_limit"] or state["tool_call_count"] >= state["max_steps"]:
        return "finalize"
    last_msg = state["messages"][-1]
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        return "tool_filter"
    return "finalize"

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
    
    result = WorkerResult(
        worker_id=state["worker_id"],
        hypothesis=state["hypothesis"],
        submitted_faults=state["submitted_faults"],
        trajectory_log=traj_str,
        execution_time=time.time() - state["start_time"],
        token_usage=state["token_usage"],
        tool_call_count=state["tool_call_count"]
    )
    return {"worker_results": [result]}

worker_workflow = StateGraph(WorkerState)
worker_workflow.add_node("think", worker_think_node)
worker_workflow.add_node("tool_filter", worker_tool_filter_node)
worker_workflow.add_node("finalize", finalize_worker)
worker_workflow.add_edge(START, "think")
worker_workflow.add_conditional_edges("think", worker_should_continue, {"tool_filter": "tool_filter", "finalize": "finalize"})
worker_workflow.add_edge("tool_filter", "think")
worker_workflow.add_edge("finalize", END)

worker_graph = worker_workflow.compile()