import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from .state import DiagnoseState, WorkerState
from .supervisor import supervisor_node
from .worker import worker_graph
from .summarizer import summarizer_node
from .inspector import global_inspector 
from .tools import search_experience, search_knowledge

async def prepare_context_node(state: DiagnoseState):
    """
    【数据准备节点】
    在图的最开始，并发执行“全局巡检(提取底层快照)”与“经验查询(基于模糊投诉)”。
    """
    if not state.get("inspector_result") and not state.get("experience_result"):
        print("🔍 [Prepare] 正在并发提取全网底层快照与 MySQL 历史成功经验...")

        # 全局巡检：包括原始的 ping、arp 检查、接口检查和 FRR 协议检查以及 LLM 总结内容        
        inspector_task = global_inspector(state)
        # 经验查询：传入问题表象，获取最多 15 条相关成功经验
        exp_task = search_experience(state["lab_name"], state["problem_info"], experience_count=15)
        
        # 并发等待结果
        res_insp, res_exp = await asyncio.gather(inspector_task, exp_task)
        print("✅ [Prepare] 巡检与经验检索完成，准备进入超级大脑...")
        
        return {
            "inspector_result": res_insp["inspector_result"], 
            "experience_result": res_exp
        }
    return {}

async def run_worker_wrapper(state: WorkerState):
    final_state = await worker_graph.ainvoke(state)
    results = final_state.get("worker_results", [])

    # 将 Worker 的 token 提取并累加到 Global State 的字典中
    # 由于 LangGraph 对于 dict 的合并默认是覆盖，我们需要写一个安全的累加合并
    tokens_to_add = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    tool_calls_to_add = 0

    for w in results:
        t = w.get("token_usage", {})
        tokens_to_add["input_tokens"] += t.get("input_tokens", 0)
        tokens_to_add["output_tokens"] += t.get("output_tokens", 0)
        tokens_to_add["total_tokens"] += t.get("total_tokens", 0)
        # 累加每个 Worker 的工具调用数
        tool_calls_to_add += w.get("tool_call_count", 0)

    return {
        "worker_results": results,
        "global_token_usage": tokens_to_add, # 在 state.py 中将 global_token_usage 设置为支持 operator.add 的合并方式
        "global_tool_calls": tool_calls_to_add
    }

# 将完结逻辑与派发逻辑合二为一，将路由节点声明为 async def
async def dispatch_workers_node(state: DiagnoseState):
    """将当轮任务派发给 Workers，或者决定走向终点"""
    # 1. 检查是否需要完结
    if state.get("next_action") == "finish" or not state.get("hypotheses"):
        print("🛑 [Dispatch] 诊断结束，正在前往 Summarizer 结算...")
        return "summarizer"
    
    # 2. 开始组装并发 Send 对象
    hypotheses = state["hypotheses"]
    print(f"🚀 [Dispatch] 唤醒 {len(hypotheses)} 个 Worker 并发执行...")
        
    sends = []
    for i, hyp in enumerate(hypotheses):
        worker_state = WorkerState(
            worker_id=f"Worker-{state['iteration_count']}-{i+1}",
            target_fault=hyp,            
            lab_name=state["lab_name"], 
            netenv_info=state["netenv_info"],
            problem_info=state["problem_info"], 
            inspector_result=state["inspector_result"],
            start_time=state["start_time"], 
            time_limit=state["time_limit"], 
            max_steps=state["max_steps"],
            messages=[], 
            tool_call_count=0, 
            token_usage={"input_tokens": 0, "output_tokens": 0, "total_tokens":0},
            submitted_result={}, 
            has_submitted=False, 
            worker_results=[]
        )
        # LangGraph 会根据这里的 Send 列表，自动起多个 Worker 节点并发执行
        sends.append(Send("run_worker_wrapper", worker_state))
        
    return sends


def build_argus_graph():
    workflow = StateGraph(DiagnoseState)
    
    workflow.add_node("inspector", prepare_context_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("run_worker_wrapper", run_worker_wrapper) 
    workflow.add_node("summarizer", summarizer_node)
    
    workflow.add_edge(START, "inspector") 
    workflow.add_edge("inspector", "supervisor")
    
    # 只保留这一个 add_conditional_edges，彻底杜绝状态错乱！
    workflow.add_conditional_edges(
        "supervisor", 
        dispatch_workers_node, 
        ["run_worker_wrapper", "summarizer"]
    )
    
    workflow.add_edge("run_worker_wrapper", "supervisor") 
    workflow.add_edge("summarizer", END)
    
    return workflow.compile()

async def diagnose_fault(
    lab_name: str, 
    netenv_info: str, 
    problem_info: str, 
    expected_faults: dict, 
    max_steps: int = 200, 
    time_limit: float = 1800.0,
) -> dict:
    import time
    print(f"\n" + "="*50)
    print(f"🚀 开始启动 Argus MAS 诊断阵列...")
    print(f"📌 诊断场景: {lab_name}")
    print(f"="*50)

    # 1. 初始化完整的最新的状态字典
    initial_state = {
        "lab_name": lab_name, 
        "netenv_info": netenv_info, 
        "problem_info": problem_info,
        "expected_faults": expected_faults, 
        "max_steps": max_steps, 
        "time_limit": time_limit,
        "start_time": time.time(), 
        
        # 新增的预热数据字段
        "inspector_result": "", 
        
        # 动态编排循环字段
        "iteration_count": 0, 
        "history_reports": [], 
        "hypotheses": [], 
        "next_action": "continue",
        
        # 结果与统计指标
        "worker_results": [], 
        "final_faults": {}, 
        "precision": 0.0, 
        "recall": 0.0,
        "trajectory": "", 
        "global_token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "global_tool_calls": 0
    }
    
    # 2. 实例化图谱
    # 👇 【关键修复】：这里必须是空参数调用！绝不能写成 build_argus_graph(lab_name=lab_name)
    app = build_argus_graph() 
    
    # 3. 运行图
    config = {"recursion_limit": max_steps}
    try:
        final_state = await app.ainvoke(initial_state, config=config)
    except Exception as e:
        print(f"\n❌ [System] 图流转因异常崩溃: {e}")
        final_state = initial_state
        
    return final_state