# src/agent/judge_agent.py
import asyncio
import os
import sys
import json
from typing import TypedDict, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

# ==========================================
# ⚙️ 路径与环境变量初始化
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

from utils.llm_models import load_model

# ==========================================
# 1. 状态定义与输出结构 (State & Schema)
# ==========================================
# 👇 【核心防御】：加入 total=False。
# 这样即使外部脚本(main.py)在传入初始状态时漏掉了某个字段，LangGraph 也绝对不会报 KeyError！
class JudgeState(TypedDict, total=False):
    """裁判智能体流转状态字典"""
    netenv_info: str               # 拓扑环境信息
    problem_info: str              # 用户的模糊投诉信息
    final_faults: dict             # 实际诊断出的复合字典 (故障名 -> 节点列表)
    precision: float               # 精确率 (体现抗噪能力)
    recall: float                  # 召回率/正确率 (体现严谨性和全面性)
    
    # 兼容两种命名方式，防止交接时报错
    tool_call_count: int           
    global_tool_calls: int         
    
    token_usage: dict              
    global_token_usage: dict       
    
    execution_time: float          # MAS 系统的总耗时
    trajectory: str                # 排查轨迹或经验
    judge_model: str               # 裁判使用的底层模型 (如 qwen3.6-big)
    
    # --- 输出字段 ---
    final_score: float              # 最终计算的总分
    subjective_reasoning: str      # 详细的判卷理由

class JudgeOutput(BaseModel):
    """
    【强制结构化输出】
    利用 Pydantic 强制大模型以特定的 JSON 格式返回各项得分与点评。
    """
    reasoning: str = Field(
        description="点评，字数请严格控制在200字以内，言简意赅，切勿长篇大论导致输出截断损坏！"
    )
    logic_score: int = Field(
        description="逻辑得分 (0-40)，评价多智能体是否合理利用了全局巡检、并行拆分，是否逻辑流畅"
    )
    efficiency_score: int = Field(
        description="效率得分 (0-30)，考察并行执行时间和 Token 开销。拓扑规模越大、故障越多，开销自然大，需酌情灵活给分"
    )
    accuracy_score: int = Field(
        description="准确得分 (0-30)，严格依据传入的 precision 和 recall 进行换算"
    )


# ==========================================
# 2. 评测智能体核心逻辑
# ==========================================
class JudgeAgent:
    # 👇 【模型升级】：默认使用你的大杯模型 qwen3.6-big 充当裁判
    def __init__(self, backend_model: str = "qwen3.6-big"):
        # 绑定 Structured Output 强制返回 JudgeOutput 结构
        self.llm = load_model(backend_model=backend_model).with_structured_output(JudgeOutput)
        
        # 严谨的裁判系统提示词
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一位资深网络故障诊断裁判。
当前评测的是先进的 【一主多从架构】：Supervisor 执行全局巡检并派发多个 Worker 并行探索假设，最后 Supervisor 汇总提交答案。
你需要基于客观指标和诊断轨迹给出满分为 100 分的评价。

评分标准：
1. 逻辑得分 (40分): 
    - 是否充分利用了全局巡检？
    - Supervisor 的假设拆分是否合理？
    - Worker 的排查轨迹是否清晰连贯？
2. 效率得分 (30分): 
    - Token 开销和工具调用数是否克制？
    - 并行机制是否显著缩短了耗时？
    - 注意：拓扑规模越大、故障注入越多， token、工具调用和耗时自然会越大，这一点需要极其酌情给分，绝对不能死板！
3. 准确得分 (30分): 
    - 一条故障和一个节点的组合，称为"一条结果"。
    - 精确率(Precision)体现抗噪能力 (0 ~ 10 分)。
    - 召回率(Recall)体现严谨性和全面性，极其重要 (0 ~ 20 分)。

注意：你必须先在 reasoning 字段输出长篇幅的详细评价，然后再给出各项分数！"""),
            ("human", """
【网络环境信息】
{netenv_info}

【用户投诉】
{problem_info}

【客观性能指标】
- Agent 最终诊断结果: {final_faults}
- 诊断精确率 (Precision): {precision}%
- 诊断召回率 (Recall): {recall}%
- 工具调用次数: {tool_call_count} 次
- 总执行耗时: {execution_time} 秒
- Token 消耗: {token_usage}

【排查轨迹与提炼经验】
{trajectory}
""")
        ])

    async def evaluate(self, **kwargs) -> dict:
        """执行异步评判链"""
        chain = self.prompt | self.llm
        try:
            # 裁判节点最多等待 600 秒 (10 分钟)
            result: JudgeOutput = await asyncio.wait_for(chain.ainvoke(kwargs), timeout=600.0)
            # 计算总分
            total = result.logic_score + result.efficiency_score + result.accuracy_score
            return {"final_score": total, "reasoning": result.reasoning}
        except asyncio.TimeoutError:
            print("❌ [Judge Agent] 裁判打分执行超时 (超过 600 秒)！")
            return {"final_score": 0, "reasoning": "LLM 裁判打分执行超时！"}
        except Exception as e:
            print(f"❌ [Judge Agent] 裁判打分发生异常: {e}")
            return {"final_score": 0, "reasoning": f"评判执行失败: {e}"}

# ==========================================
# 3. LangGraph 节点与图构建
# ==========================================
async def evaluate_node(state: JudgeState):
    """
    【图节点函数】
    提取状态字典中的数据喂给裁判 Agent，并将评判结果写回状态字典。
    """
    print("\n" + "="*50)
    print("🧑‍⚖️ [终极裁判] 正在审阅案卷，请稍候...")
    
    judge_model_name = state.get("judge_model", "qwen3.6-big")
    judge = JudgeAgent(backend_model=judge_model_name)
    
    # 👇 【极度防呆的字段提取】：兼顾新老命名字段，防止 NoneType 和 KeyError
    t_calls = state.get("global_tool_calls") or state.get("tool_call_count") or 0
    t_usage = state.get("global_token_usage") or state.get("token_usage") or {}
    
    precision_val = state.get("precision")
    if precision_val is None: precision_val = 0.0
    
    recall_val = state.get("recall")
    if recall_val is None: recall_val = 0.0
    
    # 格式化输入给大模型
    res = await judge.evaluate(
        netenv_info=state.get("netenv_info", "未知拓扑"),
        problem_info=state.get("problem_info", "未知投诉"),
        final_faults=json.dumps(state.get("final_faults", {}), ensure_ascii=False),
        precision=precision_val,
        recall=recall_val,
        tool_call_count=t_calls,
        execution_time=state.get("execution_time") or 0.0,
        token_usage=json.dumps(t_usage, ensure_ascii=False),
        trajectory=state.get("trajectory", "无轨迹记录")
    )
    
    # 👇 【沉浸式打印】：控制台华丽收尾
    print("📜 裁判最终判决书 📜")
    print(f"🏅 【最终综合得分】: {res['final_score']} / 100 分\n")
    print(f"📝 【详细判卷理由】:\n{res['reasoning']}")
    print("="*50 + "\n")
    
    return {
        "final_score": res["final_score"], 
        "subjective_reasoning": res["reasoning"]
    }

def build_judge_graph():
    """构建极简裁判单节点图"""
    workflow = StateGraph(JudgeState)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_edge(START, "evaluate")
    workflow.add_edge("evaluate", END)
    return workflow.compile()