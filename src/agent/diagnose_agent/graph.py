import time
from langgraph.graph import StateGraph, START, END
from .state import DiagnoseState
from .supervisor import supervisor_node, trigger_parallel_workers
from .worker import worker_graph
from .synthesizer import synthesizer_node
from .tools import prewarm_diagnose_caches, cleanup_mcp_client

def build_argus_graph():
    workflow = StateGraph(DiagnoseState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("worker_graph", worker_graph)
    workflow.add_node("synthesizer", synthesizer_node)
    
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges("supervisor", trigger_parallel_workers, ["worker_graph"])
    workflow.add_edge("worker_graph", "synthesizer")
    workflow.add_edge("synthesizer", END)
    return workflow.compile()

async def diagnose_fault(
    lab_name: str,
    netenv_info: str,
    problem_info: str,
    expected_faults: dict, # ⚠️ 注意参数类型变为 dict，例如 {"link_loss": ["h1", "h2"]}
    backend_model: str = "qwen3.5-27b",
    max_steps: int = 20,
    time_limit: float = 400.0,
) -> dict:
    print("\n" + "="*80)
    print("🛡️ Argus 复合诊断并行阵列启动".center(75))
    print("="*80)
    
    # 【新增】主流程开始前，强制预热所有工具和知识库缓存
    await prewarm_diagnose_caches(lab_name)

    initial_state = {
        "lab_name": lab_name,
        "netenv_info": netenv_info,
        "problem_info": problem_info,
        "backend_model": backend_model,
        "max_steps": max_steps,
        "time_limit": time_limit,
        "expected_faults": expected_faults,
        "start_time": time.time(),
        "hypotheses": [],
        "worker_results": [],
        "final_submitted_faults": {},
        "accuracy_metrics": {},
        "global_trajectory": "",
        "global_token_usage": {},
        "global_tool_calls": 0
    }
    
    graph = build_argus_graph()
    try:
        final_state = await graph.ainvoke(initial_state)
    finally:
        await cleanup_mcp_client()
        
    execution_time = time.time() - initial_state["start_time"]
    metrics = final_state.get("accuracy_metrics", {})
    
    print("\n" + "="*80)
    print("📊 Argus 全局战报".center(78))
    print("="*80)
    print(f"⏱️ 总计耗时: {execution_time:.2f} 秒")
    print(f"🔧 全局工具调用: {final_state.get('global_tool_calls', 0)} 次")
    print(f"🪙 Token 开销: {final_state.get('global_token_usage', {}).get('total_tokens', 0)}")
    print(f"🎯 准确率(Precision): {metrics.get('precision', 0):.2%} | 召回率(Recall): {metrics.get('recall', 0):.2%}")
    print(f"🤖 LLM 裁判评价:\n{final_state.get('logic_evaluation')}")
    print("="*80)
    
    return {
        "final_faults": final_state.get("final_submitted_faults"),
        "metrics": metrics,
        "execution_time": execution_time,
        "tool_call_count": final_state.get("global_tool_calls"),
        "token_usage": final_state.get("global_token_usage"),
        "trajectory": final_state.get("global_trajectory") # Judge Agent 所需的燃料
    }