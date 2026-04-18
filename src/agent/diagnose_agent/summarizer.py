import json
from langchain_core.messages import HumanMessage
from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.llm_models import load_model
from .state import DiagnoseState

def _dict_to_flat_set(fault_dict: dict) -> set:
    """
    把字典拍扁成集合，便于比对准确率和召回率
    """
    flat = set()
    for fault, nodes in fault_dict.items():
        if isinstance(nodes, list):
            for node in nodes:
                flat.add((str(fault).strip(), str(node).strip()))
    return flat

async def summarizer_node(state: DiagnoseState):
    """
    【计算指标与经验沉淀】
    负责算准确率/精确率，并调用 Big 模型从杂乱的轨迹中提取标准化 JSON 写入 SQL。
    """
    print("\n" + "="*60)
    print("📝 [Summarizer] 正在计算评测指标并抽取经验入库...")
    
    results = state.get("worker_results", [])
    
    # 1. 直接获取 Synthesizer 产出的答案
    final_submitted = state.get("final_faults", {})
            
    # 2. 计算指标
    expected_set = _dict_to_flat_set(state["expected_faults"])
    submitted_set = _dict_to_flat_set(final_submitted)
    correct_pairs = len(expected_set & submitted_set)
    precision = (correct_pairs / len(submitted_set)) if submitted_set else 0.0
    recall = (correct_pairs / len(expected_set)) if expected_set else 0.0

    # 3. 统计消耗与拼装全局原始轨迹
    total_tokens = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    total_tools = 0
    full_trajectory_logs = [state["problem_info"]] # 把用户投诉传进诊断轨迹
    
    for w in results:
        total_tokens["input_tokens"] += w["token_usage"]["input_tokens"]
        total_tokens["output_tokens"] += w["token_usage"]["output_tokens"]
        total_tools += w["tool_call_count"]
        full_trajectory_logs.append(f"--- 【{w['worker_id']}】({w['hypothesis']}) ---\n{w['trajectory_log']}")
        
    total_tokens["total_tokens"] = total_tokens["input_tokens"] + total_tokens["output_tokens"]
    global_trajectory = "\n\n".join(full_trajectory_logs)

    # 4. 调用 Big 模型，结构化提取正确的排查流写入 SQL
    # 【注意】这里必须使用 qwen3.5-big 来保证 JSON 输出的准确性
    if submitted_set:
        print("🤖 [Summarizer] 正在调用 Big 模型抽取结构化经验...")
        llm = load_model(backend_model="qwen3.5-big")
        extract_prompt = f"""
        请从以下用户投诉+并行诊断记录中，提取出 **一条或多条** **成功发现故障** 的 React(Thought-Action-Observation) 逻辑步骤。
        要求输出为一个包含模糊投诉、故障名和关键步骤的 JSON 数组格式：
        [{{
            "fuzzy_complaint": "填入这一条经验对应的用户投诉",
            "fault_name": "填入故障名称",
            "key_actions": "填入关键诊断流程，如 [Thought]: ...\\n[Action]: ...\\n[Observation]: ..."
        }}]
        例如：
        [{{
            "fuzzy_complaint": "网速慢，卡顿",
            "fault_name": "link_latency",
            "key_actions": "
[Thought]: 根据全局巡检结果，h2 与其他节点通信延迟极高而其他正常，怀疑 h2 主机存在链路延迟注入规则
[Action]: node_execute(node=h2, cli_cmd=tc qdisc show)
[Observation]: 发现 tos1_1 接口配置了 netem 规则，注入了 500.0ms 的延迟

[Thought]: 为验证延迟注入对实际通信的影响，执行 ping 测试确认 RTT 数值
[Action]: node_execute(node=h2, cli_cmd=ping -c 5 192.168.1.2)
[Observation]: ping 测试 RTT 平均值约 500ms，与 tc 配置的延迟值完全吻合且无丢包

[Thought]: 确认故障根因为 h2 主机接口上的链路延迟配置，提交最终诊断结果
[Action]: submit_diagnosis(fault_location=h2, root_cause=link_latency)
[Observation]: 诊断完成，确认故障位置为 h2，根因为 link_latency 
            "
        }}]        
        必须保持极简，只提取最核心且**正确**的步骤，剥离掉无关的错误尝试。
        标准答案：\n{state["expected_faults"]}
        诊断结果：\n{state["final_faults"]}
        诊断记录：\n{global_trajectory}
        """
        try:
            ext_res = await llm.ainvoke([HumanMessage(content=extract_prompt)])
            clean_json_str = ext_res.content.replace("```json", "").replace("```", "").strip()
            extracted_cases = json.loads(clean_json_str)
            
            mysql_db = DiagnoseExperienceBase()
            for case in extracted_cases:
                await mysql_db.insert_case(
                    lab_name=state["lab_name"],
                    fuzzy_complaint=case.get("fuzzy_complaint", "未知"),
                    root_cause=case.get("fault_name", "未知"),
                    key_actions=case.get("key_actions", "")
                )
            print("💾 [Summarizer] 标准化经验入库成功！")
        except Exception as e:
            print(f"⚠️ [Summarizer] 经验提取或入库异常 (跳过): {e}")

    return {
        "final_faults": final_submitted,
        "precision": precision,
        "recall": recall,
        "trajectory": global_trajectory,
        "global_token_usage": total_tokens,
        "global_tool_calls": total_tools
    }