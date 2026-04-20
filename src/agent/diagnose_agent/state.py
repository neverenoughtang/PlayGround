import operator
from typing import TypedDict, Annotated, Sequence, List, Dict
from langchain_core.messages import BaseMessage

class WorkerResult(TypedDict):
    """单个诊断 Worker 的提交结果"""
    worker_id: str
    hypothesis: str
    submitted_faults: Dict[str, List[str]] 
    trajectory_log: str          # 纯净的 ReAct 执行轨迹(去除了System Prompt)
    execution_time: float
    token_usage: dict
    tool_call_count: int

class DiagnoseState(TypedDict):
    """全局主状态"""
    lab_name: str
    netenv_info: str
    problem_info: str
    expected_faults: Dict[str, List[str]]
    max_steps: int
    time_limit: float
    start_time: float
    
    # --- Superviser 的产出 ---
    inspector_result: str        # global_inspector 的全局巡检结果
    hypotheses: List[str]        # supervisor 拆分的故障假设
    
    # --- Worker 并行汇聚结果 ---
    worker_results: Annotated[List[WorkerResult], operator.add] # 可以累加
    
    # --- Synthesizer 的产出 ---
    final_faults: Dict[str, List[str]] # 聚合后的最终诊断答案

    # --- Summarizer 最终计算出的指标 ---
    precision: float             # 准确率
    recall: float                # 正确率 (召回率)
    trajectory: str              # 整合后的多 Worker 纯净轨迹
    global_execution_time: float
    global_tool_calls: int
    global_token_usage: dict

class WorkerState(TypedDict):
    """子智能体（Worker）内部局部状态"""
    worker_id: str
    hypothesis: str

    lab_name: str
    netenv_info: str
    problem_info: str
    
    inspector_result: str        # Worker 可以直接读取全局巡检结果
    start_time: float
    time_limit: float
    max_steps: int
    
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tool_call_count: int
    token_usage: dict
    submitted_faults: Dict[str, List[str]]
    has_submitted: bool