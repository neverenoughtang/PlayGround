import json
from langchain_core.messages import HumanMessage
from langgraph.constants import Send
from utils.llm_models import load_model
from .state import DiagnoseState, WorkerState

async def supervisor_node(state: DiagnoseState):
    """
    根据用户投诉，将可能存在的“复合故障”拆分为多个独立的排查维度（假设域），分配给多个 Worker。
    """
    print("\n" + "👑 [Supervisor] 正在分析投诉，拆解复合故障假设域...")
    llm = load_model(backend_model=state["backend_model"])
    
    prompt = f"""
    当前拓扑：{state["lab_name"]}。用户投诉：{state["problem_info"]}。
    网络中可能存在**多种故障叠加**(复合故障)。请将排查工作划分为 2 到 3 个不重叠的【诊断假设域】。
    例如：["假设域A：排查物理层和链路拥塞丢包", "假设域B：排查路由协议(FRR/BGP)配置异常", "假设域C：排查主机网络配置与AI应用层"]。
    请直接输出 JSON 格式（必须包含 "hypotheses" 数组）。
    """
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        clean_json = res.content.replace("```json", "").replace("```", "").strip()
        hypotheses = json.loads(clean_json).get("hypotheses", ["假设域A: 主机与链路层", "假设域B: 路由与控制层"])
    except:
        hypotheses = ["假设域A: 物理链路层故障", "假设域B: 动态路由/SDN控制面故障"]
        
    print(f"👑 [Supervisor] 划分了 {len(hypotheses)} 个并行假设域：{hypotheses}")
    return {"hypotheses": hypotheses}

def trigger_parallel_workers(state: DiagnoseState):
    sends = []
    for i, hypothesis in enumerate(state["hypotheses"]):
        worker_state = WorkerState(
            worker_id=f"Worker-{i+1}",
            hypothesis=hypothesis,
            lab_name=state["lab_name"],
            netenv_info=state["netenv_info"],
            problem_info=state["problem_info"],
            backend_model=state["backend_model"],
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