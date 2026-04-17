import time, json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from utils.llm_models import load_model
from .state import WorkerState, WorkerResult
from .tools import create_smart_tools

async def worker_think_node(state: WorkerState):
    """诊断专家思考与决策节点"""
    print(f"\n🧠 [{state['worker_id']}] 正在基于【{state['hypothesis']}】进行推理...")
    tools = await create_smart_tools(state)
    llm = load_model(backend_model=state["backend_model"]).bind_tools(tools)
    
    if not state["messages"]:
        sys_prompt = f"""你是独立网络排障专家。负责排查的领域：【{state['hypothesis']}】
        网络拓扑：{state['netenv_info']}
        用户投诉：{state['problem_info']}
        
        工作流要求：
        1. 优先调用 global_inspector_tool()，遇到卡点调用 smart_mentor_tool()。
        2. 使用基础 CLI 工具验证假设。
        3. 你的领域内可能包含多个故障节点，也可能没有。查清后，必须调用 submit_diagnosis(faults_json_str) 结束。
        传入格式示例：'{{"link_loss": ["h1"], "interface_down": ["r1", "r2"]}}'。
        """
        messages = [HumanMessage(content=sys_prompt)]
    else:
        messages = list(state["messages"])
        
    response = await llm.ainvoke(messages)
    
    usage = dict(state["token_usage"])
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage["input_tokens"] += response.usage_metadata.get("input_tokens", 0)
        usage["output_tokens"] += response.usage_metadata.get("output_tokens", 0)
    
    return {"messages": [response], "token_usage": usage}

async def worker_tool_filter_node(state: WorkerState):
    """【工具过滤器节点】批量执行工具，并自动对冗长回显进行摘要截断"""
    last_msg = state["messages"][-1]
    if not (hasattr(last_msg, 'tool_calls') and last_msg.tool_calls):
        return {}

    tools = await create_smart_tools(state)
    tool_map = {t.name: t for t in tools}
    
    results = []
    tool_count = state["tool_call_count"]
    has_sub = state["has_submitted"]
    sub_faults = state["submitted_faults"]
    usage = dict(state["token_usage"])
    
    for tc in last_msg.tool_calls:
        tool_count += 1
        t_name = tc["name"]
        t_args = tc["args"]
        print(f"🔧 [{state['worker_id']}] 执行工具: {t_name}")
        
        # 拦截提交答案行为
        if t_name == "submit_diagnosis":
            has_sub = True
            try:
                # 尝试解析传进来的 JSON 字符串
                json_str = t_args.get("faults_json_str", "{}")
                sub_faults = json.loads(json_str)
                print(f"🎯 [{state['worker_id']}] 提交了域内诊断: {sub_faults}")
            except Exception as e:
                print(f"⚠️ [{state['worker_id']}] JSON 格式错误: {e}")
            results.append(ToolMessage(tool_call_id=tc["id"], name=t_name, content="提交成功，流程结束。"))
            continue

        # 执行实际工具
        t_func = tool_map.get(t_name)
        try:
            raw_output = await t_func.ainvoke(t_args)
            raw_str = str(raw_output)
        except Exception as e:
            results.append(ToolMessage(tool_call_id=tc["id"], name=t_name, content=f"[执行失败] {e}"))
            continue

        # 【核心智能过滤】
        if len(raw_str) > 100:
            print(f"   ⚠️ 输出过长({len(raw_str)}字符)，调用 LLM 过滤关键异常...")
            llm = load_model(backend_model=state["backend_model"])
            prompt = f"工具 {t_name} 输出极长。请严格提取包含 'DOWN', 'error', 'fail', 'timeout', 'unreachable', 'Idle' 等网络异常信息的行及上下文(限300字)，如果完全正常则回答'运行正常，无明显异常'。\n原始输出片段：\n{raw_str[:3000]}"
            summary_res = await llm.ainvoke([HumanMessage(content=prompt)])
            
            if hasattr(summary_res, 'usage_metadata') and summary_res.usage_metadata:
                usage["input_tokens"] += summary_res.usage_metadata.get("input_tokens", 0)
                usage["output_tokens"] += summary_res.usage_metadata.get("output_tokens", 0)
                
            final_content = f"[已智能截断摘要]: {summary_res.content}"
        else:
            final_content = raw_str
            
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
    result = WorkerResult(
        worker_id=state["worker_id"],
        hypothesis=state["hypothesis"],
        submitted_faults=state["submitted_faults"],
        trajectory=state["messages"],
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