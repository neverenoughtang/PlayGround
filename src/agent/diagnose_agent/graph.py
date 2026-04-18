import time
from langgraph.graph import StateGraph, START, END
# 【修复】使用最新的 LangGraph Types Send 接口
from langgraph.types import Send

from tmx.Argus.src.agent.diagnose_agent.synthesizer import synthesizer_node 

from .state import DiagnoseState, WorkerState
from .supervisor import supervisor_node
from .worker import worker_graph
from .summarizer import summarizer_node
from .tools import cleanup_mcp_client

def dispatch_workers_node(state: DiagnoseState):
    """
    【汇聚与派发】
    当 Inspector(巡检) 和 Supervisor(拆解) 均完成后，该节点执行。
    将巡检结果和拆解任务派发给并行的 Worker 集群。
    """
    print("\n🚀 [Dispatch] 正在激活 Worker 集群并发执行...")
    sends = []
    for i, hypothesis in enumerate(state["hypotheses"]):
        worker_state = WorkerState(
            worker_id=f"Worker-{i+1}",
            hypothesis=hypothesis,
            lab_name=state["lab_name"],
            netenv_info=state["netenv_info"],
            problem_info=state["problem_info"],
            inspector_result=state["inspector_result"],
            start_time=state["start_time"],
            time_limit=state["time_limit"],
            max_steps=state["max_steps"],
            messages=[],
            tool_call_count=0,
            token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            submitted_faults={},
            has_submitted=False,
            worker_results=[]
        )
        sends.append(Send("worker_graph", worker_state))
    return sends

def build_argus_graph():
    workflow = StateGraph(DiagnoseState)
    
    # 注册节点
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("worker_graph", worker_graph) # Send 不作为传统节点，而是置于 conditional_edges 的派发函数中
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("summarizer", summarizer_node)
    
    # 定义工作流
    workflow.add_edge(START, "supervisor") 
    workflow.add_conditional_edges("supervisor", dispatch_workers_node, ["worker_graph"]) # 从同步点触发并发 Send
    workflow.add_edge("worker_graph", "synthesizer") # 总结并提交答案
    workflow.add_edge("synthesizer", "summarizer")
    workflow.add_edge("summarizer", END)
    
    return workflow.compile()

async def diagnose_fault(
    lab_name: str,
    netenv_info: str,
    problem_info: str,
    expected_faults: dict,
    max_steps: int = 15,
    time_limit: float = 400.0,
) -> dict:
    
    print("\n" + "="*80)
    print("🛡️ Argus 多智能体并发诊断阵列启动 (含全网巡检)".center(75))
    print("="*80)
    
    initial_state = {
        "lab_name": lab_name,
        "netenv_info": netenv_info,
        "problem_info": problem_info,
        "expected_faults": expected_faults,
        "max_steps": max_steps,
        "time_limit": time_limit,
        "start_time": time.time(),
        "inspector_result": "",
        "hypotheses": [],
        "worker_results": [],
        "final_faults": {},
        "precision": 0.0,
        "recall": 0.0,
        "trajectory": "",
        "global_token_usage": {},
        "global_tool_calls": 0
    }
    
    graph = build_argus_graph()
    try:
        final_state = await graph.ainvoke(initial_state)
    finally:
        await cleanup_mcp_client()
        
    execution_time = time.time() - initial_state["start_time"]
    
    print("\n" + "="*80)
    print("📊 Argus 全局战报".center(78))
    print("="*80)
    print(f"⏱️ 总耗时: {execution_time:.2f} 秒")
    print(f"🔧 总工具调用: {final_state.get('global_tool_calls')} 次")
    print(f"🪙 Token消耗: {final_state.get('global_token_usage', {}).get('total_tokens')}")
    print(f"🎯 精确率(Precision): {final_state.get('precision', 0):.2%} | 正确率(Recall): {final_state.get('recall', 0):.2%}")
    print("="*80)
    
    return {
        "final_faults": final_state.get("final_faults"),
        "precision": final_state.get("precision"),
        "recall": final_state.get("recall"),
        "execution_time": execution_time,
        "tool_call_count": final_state.get("global_tool_calls"),
        "token_usage": final_state.get("global_token_usage"),
        "trajectory": final_state.get("trajectory")
    }