import asyncio
import os
import sys
from typing import TypedDict
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

# 导入本地模型加载器和日志
from utils.llm_models import load_model

# ==========================================
# 1. 状态定义与输出结构
# ==========================================
class JudgeState(TypedDict):
    netenv_info: str
    problem_info: str
    expected_fault: str
    expected_location: str          # 【新增】期望故障位置
    diagnosis_result: str
    fault_location: str              # 【新增】实际故障位置
    location_correct: bool           # 【新增】位置是否正确
    attribution_correct: bool        # 【新增】归因是否正确
    tool_call_count: int             # 【新增】工具调用次数
    execution_time: float            # 【新增】执行时间
    token_usage: dict                # 【新增】Token 消耗
    trajectory: str
    judge_model: str
    
    # 输出字段
    综合_score: float                # 【修改】改为浮点数，范围 0-100
    subjective_reasoning: str

# 强制结构化输出的数据模型
class EvaluationOutput(BaseModel):
    logic_score: int = Field(description="逻辑推理得分（0-40分）：推导链路是否清晰、合理。")
    efficiency_score: int = Field(description="效率得分（0-30分）：是否存在冗余工具调用、死循环。")
    accuracy_bonus: int = Field(description="准确性得分（0-30分）：位置和归因是否正确的加分项。")
    reasoning: str = Field(description="详细的打分理由，必须分点说明逻辑、效率、准确性三方面的表现。")

# ==========================================
# 2. 智能体节点 (Nodes)
# ==========================================
class JudgeAgent:
    """
    客观+主观评价智能体：基于诊断轨迹给 Diagnose Agent 打分
    """
    
    def __init__(self, backend_model: str = "qwen3.5-27b"):
        # 强制结构化输出，确保 100% 返回可解析的 JSON
        raw_llm = load_model(backend_model=backend_model)
        self.evaluator_llm = raw_llm.with_structured_output(EvaluationOutput)
        
    async def evaluate(self, netenv_info: str, problem_info: str, location_correct: str, attribution_correct: str, 
                       expected_location: str, expected_fault: str, fault_location: str, diagnosis_result: str, trajectory: str, 
                       tool_call_count: int, execution_time: float, token_usage: dict, timeout: int = 600) -> dict:
        
        prompt_template = ChatPromptTemplate.from_messages([
("system", 
"""你是一位资深的网络安全与网络架构评审专家。
你的任务是综合【客观指标】和【主观评价】，对 AI 诊断智能体的表现进行全面打分。

【评分维度】（总分 100 分）
1. **逻辑推理得分（0-50分）**
   - 思路是否清晰、有条理，由浅入深诊断
   - 工具调用是否符合诊断逻辑链，否存在冗余工具调用（同样工具+参数重复调用）
   - 是否陷入死循环或无意义的探索

2. **效率得分（0-20分）**
   - 是否能快速锁定故障范围，节约时间（注意由于网络性能较差，执行时间通常在 100s 以上，具体打分依拓扑规模而定）（0-10分）
   - 是否语言简洁，节约 token（注意由于多智能体系统模块多而且各个模块系统提示词较长，token 消耗通常在 50k 以上，具体打分依拓扑规模而定）（0-10分）

3. **准确性加分（0-30分）**
   - 故障位置是否正确（满分 15 分）
   - 故障归因是否正确（满分 15 分）

【客观参考指标】
- 工具调用次数：{tool_call_count} 次
- 执行时间：{execution_time:.2f} 秒
- Token 消耗：{token_usage_total} tokens
- 位置正确性：{location_status}
- 归因正确性：{attribution_status}

【输出要求】
- 必须使用中文
- reasoning 字段必须分三点说明逻辑、效率、准确性的表现
- 三个分数加起来不超过 100 分
"""),
("user", 
"""--- 诊断任务信息 ---
【网络拓扑信息】
{netenv_info}

【故障现象描述】
{problem_info}

【期望故障位置】
{expected_location}

【期望故障根因】
{expected_fault}

【Agent 实际诊断位置】
{fault_location}

【Agent 实际诊断根因】
{diagnosis_result}

【Agent 诊断轨迹】
{trajectory}

请根据上述信息，给出你的评分（logic_score, efficiency_score, accuracy_bonus）和详细理由（reasoning）。
""")
    ])
        
        # 计算客观指标
        location_status = "✅ 正确" if location_correct else "❌ 错误"
        attribution_status = "✅ 正确" if attribution_correct else "❌ 错误"
        
        chain = prompt_template | self.evaluator_llm
        
        try:
            result: EvaluationOutput = await asyncio.wait_for(chain.ainvoke({
                "netenv_info": netenv_info,
                "problem_info": problem_info,
                "expected_location": expected_location,
                "expected_fault": expected_fault,
                "fault_location": fault_location,
                "diagnosis_result": diagnosis_result,
                "trajectory": trajectory,
                "tool_call_count": tool_call_count,
                "execution_time": execution_time,
                "token_usage_total": token_usage.get("total_tokens", 0),
                "location_status": location_status,
                "attribution_status": attribution_status
            }), timeout=timeout)
            
            # 计算综合得分
            total_score = result.logic_score + result.efficiency_score + result.accuracy_bonus
            
            return {
                "综合_score": total_score,
                "logic_score": result.logic_score,
                "efficiency_score": result.efficiency_score,
                "accuracy_bonus": result.accuracy_bonus,
                "reasoning": result.reasoning
            }
        
        except asyncio.TimeoutError:
            return {"综合_score": 0, "reasoning": f"LLM 裁判打分执行超时 ({timeout} 秒)！"}
        except Exception as e:
            return {"综合_score": 0, "reasoning": f"评判执行失败: {e}"}
        
async def evaluate_node(state: JudgeState):
    judge = JudgeAgent(backend_model=state["judge_model"])
    res = await judge.evaluate(
        netenv_info=state["netenv_info"],
        problem_info=state["problem_info"],
        expected_location=state["expected_location"],     # 【新增】
        expected_fault=state["expected_fault"],
        fault_location=state["fault_location"],           # 【新增】
        diagnosis_result=state["diagnosis_result"],
        location_correct=state["location_correct"],       # 【新增】
        attribution_correct=state["attribution_correct"], # 【新增】
        tool_call_count=state["tool_call_count"],         # 【新增】
        execution_time=state["execution_time"],           # 【新增】
        token_usage=state["token_usage"],                 # 【新增】
        trajectory=state["trajectory"]
    )
    return {
        "综合_score": res["综合_score"],
        "subjective_reasoning": res["reasoning"]
    }

# ==========================================
# 3. 构建子图
# ==========================================
def build_judge_graph():
    workflow = StateGraph(JudgeState)
    workflow.add_node("evaluate_node", evaluate_node)
    
    workflow.add_edge(START, "evaluate_node")
    workflow.add_edge("evaluate_node", END)
    return workflow.compile()