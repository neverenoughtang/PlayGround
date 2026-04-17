import operator
from typing import TypedDict, Annotated, Sequence, List, Dict
from langchain_core.messages import BaseMessage

class WorkerResult(TypedDict):
    """单个 Worker 提交的诊断结果"""
    worker_id: str
    hypothesis: str
    submitted_faults: Dict[str, List[str]] # e.g. {"link_loss": ["h1", "h3"]}
    trajectory: Sequence[BaseMessage]
    execution_time: float
    token_usage: dict
    tool_call_count: int

class DiagnoseState(TypedDict):
    """全局主状态"""
    lab_name: str
    netenv_info: str
    problem_info: str
    backend_model: str
    max_steps: int
    time_limit: float
    
    # 期望的复合故障配置字典
    expected_faults: Dict[str, List[str]] 
    
    # 内部流转状态
    start_time: float
    hypotheses: List[str]
    worker_results: Annotated[List[WorkerResult], operator.add]
    
    # 最终输出与评价指标
    final_submitted_faults: Dict[str, List[str]]
    accuracy_metrics: dict  # 包含准确率、正确率等
    global_trajectory: str
    global_token_usage: dict
    global_execution_time: float
    global_tool_calls: int

class WorkerState(TypedDict):
    """Worker 局部状态"""
    worker_id: str
    hypothesis: str
    lab_name: str
    netenv_info: str
    problem_info: str
    backend_model: str
    start_time: float
    time_limit: float
    max_steps: int
    
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tool_call_count: int
    token_usage: dict
    
    # Worker 自己的提交结果
    submitted_faults: Dict[str, List[str]]
    has_submitted: bool
    
    worker_results: Annotated[List[WorkerResult], operator.add]