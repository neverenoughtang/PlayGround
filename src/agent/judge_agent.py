import asyncio
import os
import sys
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils.llm_models import load_model

# 强制结构化输出的数据模型
class EvaluationOutput(BaseModel):
    score: int = Field(description="对 Agent 排查逻辑的打分，范围 0 到 10 分。")
    reasoning: str = Field(description="详细的打分理由，包括其推导是否合理、工具使用是否冗余等。")

class JudgeAgent:
    """主观评价智能体：基于诊断轨迹给 React Agent 打分"""
    
    def __init__(self, backend_model: str = "qwen3.5-27b"):
        # 强制结构化输出，确保 100% 返回可解析的 JSON
        raw_llm = load_model(backend_model=backend_model)
        self.evaluator_llm = raw_llm.with_structured_output(EvaluationOutput)
        
    async def evaluate(self, netenv_info: str, problem_info: str, expected_fault: str, diagnosis_result: str, trajectory: str, timeout: int = 600) -> dict:
        prompt_template = ChatPromptTemplate.from_messages([
("system", 
"""你是一位资深的网络安全与网络架构评审专家。
你的任务是审查一个 AI 助手排查网络故障的全过程，并对其【排障逻辑】进行严谨打分（0-10分）。

【评分标准】
- 10分：逻辑极其清晰，工具调用精准无废话，完美且迅速地锁定了根因。
- 7-9分：思路正确且找到了根因，但中间有轻微的工具绕路或无用尝试。
- 4-6分：虽然可能得出了正确结论，但推理过程存在牵强附会；或者逻辑正确但最终因环境因素提交错误。
- 0-3分：毫无逻辑的乱调用，死循环，或者得出了南辕北辙的荒谬结论。

【输出要求】
- 请结合提供的真实故障根因、Agent最终提交结果以及排查轨迹，给出你的 score 和 reasoning。
- 必须使用中文!
"""),
("user", 
 """--- 任务信息 ---
【网络拓朴信息】
{netenv_info}
【故障现象描述】
{problem_info}
【真实预期故障根因】
{expected_fault}
【Agent 最终诊断结果】
{diagnosis_result}
【Agent 诊断轨迹 (Trajectory)】
{trajectory}
""")
        ])
        
        chain = prompt_template | self.evaluator_llm
        
        try:
            result: EvaluationOutput = await asyncio.wait_for(chain.ainvoke({
                "netenv_info": netenv_info,
                "problem_info": problem_info,
                "expected_fault": expected_fault,
                "diagnosis_result": diagnosis_result,
                "trajectory": trajectory
            }),
            timeout=timeout) # 超时报错机制！
            return {"score": result.score, "reasoning": result.reasoning}

        # 新增超时捕获分支
        except asyncio.TimeoutError:
            return {"score": 0, "reasoning": f"LLM 裁判打分执行超时 ({timeout} 秒)！"}
        
        except Exception as e:
            # 兜底机制：若模型未严格遵守结构化输出
            return {"score": 0, "reasoning": f"评判执行失败: {e}"}