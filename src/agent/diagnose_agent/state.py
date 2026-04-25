import operator
from typing import TypedDict, Annotated, Sequence, List, Dict
from langchain_core.messages import BaseMessage


# 无论传入什么妖魔鬼怪，都能安全合并成列表，遇到 CLEAR 就清空
def invincible_list_adder(left, right):
    if right == "CLEAR": return []
    res = left if left is not None else []
    if not isinstance(res, list): res = [res]
    
    if not right: return res
    if isinstance(right, list): return res + right
    return res + [right]

# Token 累加器 (保持不变)
def add_token_usage(left: dict, right: dict) -> dict:
    if not left: left = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if not right: return left
    return {
        "input_tokens": left.get("input_tokens", 0) + right.get("input_tokens", 0),
        "output_tokens": left.get("output_tokens", 0) + right.get("output_tokens", 0),
        "total_tokens": left.get("total_tokens", 0) + right.get("total_tokens", 0)
    }

# 一个安全的整数累加器，防止 None 导致崩溃
def add_int(left: int, right: int) -> int:
    if left is None: left = 0
    if right is None: right = 0
    return left + right

class WorkerResult(TypedDict):
    """单个诊断 Worker 的提交结果"""
    worker_id: str
    target_fault: str            # 【修改】Worker 现在只针对一种假设故障
    existing: bool               # 【新增】是否存在该故障
    location: List[str]          # 【修改】故障节点列表
    reason: str                  # 【新增】诊断推理理由
    trajectory_log: str          
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
    
    inspector_result: str        
    experience_result: str       
    
    iteration_count: int
    next_action: str
    hypotheses: List[str]        
    
    history_reports: Annotated[List[str], invincible_list_adder] 
    worker_results: Annotated[List[WorkerResult], invincible_list_adder] 
    
    final_faults: Dict[str, List[str]]
    global_token_usage: Annotated[dict, add_token_usage]
    global_tool_calls: Annotated[int, add_int]
    precision: float
    recall: float
    trajectory: str

class WorkerState(TypedDict):
    """子智能体（Worker）内部局部状态"""
    worker_id: str
    target_fault: str            # 只负责一种故障

    lab_name: str
    netenv_info: str
    problem_info: str
    inspector_result: str        # Worker 可以直接读取全局巡检结果

    messages: Annotated[List[BaseMessage], operator.add]

    start_time: float
    time_limit: float
    max_steps: int
    tool_call_count: int
    token_usage: dict

    submitted_result: dict       
    has_submitted: bool
    worker_results: list # 子图中不需要 Reducer，直接覆盖