import asyncio
import json
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, START, END

from agent.react_agent import NetworkFaultDiagnosisAgent
from agent.judge_agent import JudgeAgent


# 1. 定义状态字典 (State)
class TestState(TypedDict):
    # --- 输入配置 ---
    lab_name: str
    netenv_info: str
    problem_info: str
    expected_fault: str
    max_steps: int
    actor_model: str
    judge_model: str
    
    # --- Node 1: React Agent 输出 ---
    diagnosis_result: str
    trajectory: str
    tool_call_count: int
    execution_time: float
    token_usage: dict
    
    # --- Node 2: 客观评价 输出 ---
    is_correct: bool
    
    # --- Node 3: 主观评价 输出 ---
    subjective_score: int
    subjective_reasoning: str


# 2. 定义节点 (Nodes)
async def diagnose_node(state: TestState):
    """节点 1：执行网络故障排查"""
    print(">>> Node 1: Running Diagnosis Agent...")
    agent = NetworkFaultDiagnosisAgent(
        lab_name=state["lab_name"],
        max_steps=state["max_steps"],
        netenv_info=state["netenv_info"],
        problem_info=state["problem_info"],
        backend_model=state["actor_model"]
    )
    res = await agent.run_diagnosis()
    return {
        "diagnosis_result": res["result"],
        "trajectory": res["trajectory"],
        "tool_call_count": res["tool_call_count"],
        "execution_time": res["execution_time"],
        "token_usage": res["token_usage"]
    }

def objective_eval_node(state: TestState):
    """节点 2：客观正确性比对"""
    print(">>> Node 2: Running Objective Evaluation...")
    # 直接比对预期结果和输出结果
    is_correct = state["expected_fault"].lower() == state["diagnosis_result"].lower()
    return {"is_correct": is_correct}

async def subjective_eval_node(state: TestState):
    """节点 3：LLM 裁判主观打分"""
    print(">>> Node 3: Running Subjective Evaluation (Judge)...")
    judge = JudgeAgent(backend_model=state["judge_model"])
    eval_res = await judge.evaluate(
        netenv_info=state["netenv_info"],
        problem_info=state["problem_info"],
        expected_fault=state["expected_fault"],
        diagnosis_result=state["diagnosis_result"],
        trajectory=state["trajectory"]
    )
    return {
        "subjective_score": eval_res["score"],
        "subjective_reasoning": eval_res["reasoning"]
    }


# 3. 编排 LangGraph
def build_agent_graph():
    workflow = StateGraph(TestState)
    
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("objective", objective_eval_node)
    workflow.add_node("subjective", subjective_eval_node)
    
    workflow.add_edge(START, "diagnose")
    workflow.add_edge("diagnose", "objective")
    workflow.add_edge("objective", "subjective")
    workflow.add_edge("subjective", END)
    
    return workflow.compile()


# ==========================================
# 独立测试入口
# ==========================================
async def main():
    # 初始化你的测试数据参数
    initial_state = {
        "lab_name": "rip_internet",
        "netenv_info": "节点: pc1, r1, r4... 链路: ...", # 填入实际拓扑文本
        "problem_info": "用户反馈网络中断",
        "expected_fault": "rip_route_filter",
        "max_steps": 10,
        "actor_model": "gemini-3-flash-preview", # 诊断 LLM
        "judge_model": "gemini-3-flash-preview"  # 裁判 LLM
    }
    
    app = build_agent_graph()
    
    # 运行流式/状态机执行
    final_state = await app.ainvoke(initial_state)
    
    # 打印最终评价报告
    print("\n" + "="*50)
    print("📊 最终评估报告")
    print("="*50)
    print(f"✅ 客观正确性: {final_state['is_correct']}")
    print(f"预期故障: {final_state['expected_fault']} | 诊断结果: {final_state['diagnosis_result']}")
    print(f"⏱️ 耗时: {final_state['execution_time']} 秒")
    print(f"🛠️ 工具调用: {final_state['tool_call_count']} 次")
    print(f"🪙 Token 消耗: {final_state['token_usage']}")
    print("-" * 50)
    print(f"🌟 主观逻辑得分: {final_state['subjective_score']} / 10")
    print(f"📝 裁判点评:\n{final_state['subjective_reasoning']}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())