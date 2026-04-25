import asyncio
import os
import sys
import json
from typing import TypedDict
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

from utils.llm_models import load_model

# ==========================================
# 1. 状态定义与输出结构
# ==========================================
class JudgeState(TypedDict):
    netenv_info: str
    problem_info: str
    final_faults: dict             # 【修改】实际诊断出的复合字典
    precision: float               # 【修改】精确率
    recall: float                  # 【修改】正确率
    tool_call_count: int
    execution_time: float
    token_usage: dict
    trajectory: str
    judge_model: str
    
    # 输出字段
    综合_score: float
    subjective_reasoning: str

class JudgeOutput(BaseModel):
    logic_score: int = Field(description="逻辑得分 (0-40)，评价多智能体是否合理利用了全局巡检、并行拆分，是否逻辑流畅")
    efficiency_score: int = Field(description="效率得分 (0-30)，考察并行执行时间和 Token 开销")
    accuracy_score: int = Field(description="准确得分 (0-30)，严格依据传入的 precision 和 recall 进行换算")
    reasoning: str = Field(description="详尽的扣分/加分点评，指出 Argus 主从架构的亮点或缺陷")

# ==========================================
# 2. 评测智能体核心
# ==========================================
class JudgeAgent:
    def __init__(self, backend_model: str = "qwen3.6-big"):
        # 裁判属于高难度推理任务，固定分配大杯模型
        self.llm = load_model(backend_model=backend_model).with_structured_output(JudgeOutput)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一位资深网络故障诊断裁判。
当前评测的是先进的 【一主多从架构】：Superviser 执行全局巡检并派发多个 Worker 并行探索假设，最后 Superviser 汇总提交答案。
你需要基于客观指标和诊断轨迹给出满分为 100 分的评价。

评分标准：
1. 逻辑得分 (40分): 
    - 是否充分利用了全局巡检？
    - Supervisor 的假设拆分是否合理？
    - Worker 的排查轨迹是否清晰连贯？
2. 效率得分 (30分): 
    - Token 开销和工具调用数是否克制？
    - 工具调用数是否克制？
    - 并行机制是否显著缩短了耗时？
    - 注意拓扑规模越大、故障注入越多， token、工具调用和耗时自然会越大，这一点需要酌情给分，不能死板！
3. 准确得分 (30分): 
    - 一条故障和一个节点的组合，称为"一条结果"
    - 精确率(Precision)为 agent 系统成功诊断出来的结果数量除以 agent 提交的全部结果数量，体现 agent 系统的抗噪能力，需要酌情给分 (0 ~ 10 分)
    - 召回率(Recall) 为 agent 系统成功诊断出来的结果数量除以正确的答案数量，体现 agent 系统的严谨性和全面性，相对重要 (0 ~ 20 分)

请直接返回严谨的 JSON 结构。"""),
            ("human", """
【网络环境信息】
{netenv_info}

【用户投诉】
{problem_info}

【客观性能指标】
- 诊断结果(JSON): {final_faults}
- 诊断精确率: {precision}
- 诊断召回率: {recall}
- 工具调用次数: {tool_call_count} 次
- 总执行耗时: {execution_time} 秒
- Token 消耗: {token_usage}

【诊断轨迹】
{trajectory}
""")
        ])

    async def evaluate(self, **kwargs):
        chain = self.prompt | self.llm
        try:
            # 裁判节点最多等待 600 秒
            result: JudgeOutput = await asyncio.wait_for(chain.ainvoke(kwargs), timeout=600.0)
            total = result.logic_score + result.efficiency_score + result.accuracy_score
            return {"综合_score": total, "reasoning": result.reasoning}
        except asyncio.TimeoutError:
            return {"综合_score": 0, "reasoning": "LLM 裁判打分执行超时！"}
        except Exception as e:
            return {"综合_score": 0, "reasoning": f"评判执行失败: {e}"}

async def evaluate_node(state: JudgeState):
    judge = JudgeAgent(backend_model=state["judge_model"])
    res = await judge.evaluate(
        netenv_info=state["netenv_info"],
        problem_info=state["problem_info"],
        final_faults=json.dumps(state["final_faults"], ensure_ascii=False),
        precision=state["precision"],
        recall=state["recall"],
        tool_call_count=state["tool_call_count"],
        execution_time=state["execution_time"],
        token_usage=state["token_usage"],
        trajectory=state["trajectory"]
    )
    return {"综合_score": res["综合_score"], "subjective_reasoning": res["reasoning"]}

def build_judge_graph():
    workflow = StateGraph(JudgeState)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_edge(START, "evaluate")
    workflow.add_edge("evaluate", END)
    return workflow.compile()