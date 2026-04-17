from langchain_core.messages import HumanMessage
from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.llm_models import load_model
from .state import DiagnoseState

def _dict_to_flat_set(fault_dict: dict) -> set:
    """将 {"loss": ["h1","h2"]} 拍平为 {("loss", "h1"), ("loss", "h2")} 以方便求交集"""
    flat = set()
    for fault, nodes in fault_dict.items():
        if isinstance(nodes, list):
            for node in nodes:
                flat.add((str(fault).strip(), str(node).strip()))
    return flat

async def synthesizer_node(state: DiagnoseState):
    print("\n" + "="*60)
    print("📝 [Synthesizer] 正在聚合多源数据并进行综合评判...")
    
    results = state.get("worker_results", [])
    
    # 1. 聚合所有 Worker 提交的字典
    final_submitted = {}
    for w in results:
        for fault, nodes in w["submitted_faults"].items():
            if fault not in final_submitted:
                final_submitted[fault] = []
            final_submitted[fault].extend(nodes)
            # 去重
            final_submitted[fault] = list(set(final_submitted[fault]))
            
    # 2. 计算准确率(Precision) 与 正确率(Recall)
    expected_set = _dict_to_flat_set(state["expected_faults"])
    submitted_set = _dict_to_flat_set(final_submitted)
    
    correct_pairs = len(expected_set & submitted_set)
    precision = (correct_pairs / len(submitted_set)) if submitted_set else 0.0
    recall = (correct_pairs / len(expected_set)) if expected_set else 0.0
    
    print(f"📊 期望的复合故障集: {expected_set}")
    print(f"📊 实际诊断的故障集: {submitted_set}")
    print(f"🎯 准确率(Precision): {precision:.2%} | 正确率/召回率(Recall): {recall:.2%}")

    # 3. 统计全局消耗
    total_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    total_tools = 0
    full_trajectory_log = []
    
    for w in results:
        total_tokens["input_tokens"] += w["token_usage"]["input_tokens"]
        total_tokens["output_tokens"] += w["token_usage"]["output_tokens"]
        total_tools += w["tool_call_count"]
        
        full_trajectory_log.append(f"\n--- 【{w['worker_id']}】 轨迹 ({w['hypothesis']}) ---")
        for msg in w["trajectory"]:
            if hasattr(msg, "content") and msg.content:
                full_trajectory_log.append(f"[Thought]: {msg.content[:200]}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    full_trajectory_log.append(f"[Action]: {tc['name']}({tc['args']})")
                    
    total_tokens["total_tokens"] = total_tokens["input_tokens"] + total_tokens["output_tokens"]
    global_trajectory = "\n".join(full_trajectory_log)

    # 4. 写入经验库 (只要有发现就写)
    if submitted_set:
        print("💾 正在将复合排障经验注入 MySQL...")
        mysql_db = DiagnoseExperienceBase()
        try:
            await mysql_db.insert_case(
                lab_name=state["lab_name"],
                fuzzy_complaint=f"{state['problem_info']} (复合故障分析)",
                root_cause=str(final_submitted),
                key_actions=global_trajectory[:2000]
            )
        except Exception as e:
            print(f"❌ 写入经验库失败: {e}")

    return {
        "final_submitted_faults": final_submitted,
        "accuracy_metrics": {"precision": precision, "recall": recall, "correct_pairs": correct_pairs},
        "global_trajectory": global_trajectory,
        "global_token_usage": total_tokens,
        "global_tool_calls": total_tools
    }