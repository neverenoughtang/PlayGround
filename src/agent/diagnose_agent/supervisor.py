import os
import re
import json
import asyncio
from langchain_core.messages import HumanMessage

from utils.llm_models import load_model
from .fault_knowledge import FAULT_REGISTRY


async def supervisor_node(state: dict):
    """
    【动态编排大脑】
    1. 审查上一轮 worker_results (如果有)
    2. 决定是继续拆解假设 (continue)，还是得出最终结论 (finish)
    """
    iteration = state.get("iteration_count", 0) + 1
    history_reports = state.get("history_reports", [])
    worker_results = state.get("worker_results", [])

    print(f"\n👑 [Supervisor] 开启第 {iteration} 轮动态编排思考...")

    # 👇 【核心修复 1：强制 5 轮熔断】
    if iteration > 5:
        print("🛑 [Supervisor] 已达到最大排查轮数 (5轮)，强制结束排查！")
        return {
            "iteration_count": iteration,
            "next_action": "finish",
            "final_faults": {"unknown_fault_timeout": []}, # 兜底答案
            "worker_results": "CLEAR"
        }
    
    # 1. 组装本轮 Worker 的原生反馈 (给大模型做阅读理解)
    current_feedback = "暂无（当前是第一轮，请直接根据巡检报告提出初始假设）。"
    if worker_results:
        current_feedback = ""
        for w in worker_results:
            status = "🔴 确诊" if w.get("existing") else "🟢 排除"
            current_feedback += f"- Worker[{w['worker_id']}] 检查 [{w['target_fault']}]: {status}。证据: {w.get('reason', '无')}\n"

    # 👇 【核心修复 2：提取黑名单，防止死循环】
    excluded_faults = set()
    history_text = "\n".join(history_reports)
    # 用正则抓取历史中被标记为排除的故障名
    matches = re.findall(r"🟢 排除 \[([^\]]+)\]", history_text + current_feedback)
    for m in matches:
        excluded_faults.add(m)
    
    black_list_str = ", ".join(excluded_faults) if excluded_faults else "无"

    # 2. 组装可用故障知识库
    relevant_faults = ""
    for category in ["common_link", "common_host", state["lab_name"]]:
        if category in FAULT_REGISTRY:
            relevant_faults += FAULT_REGISTRY[category] + "\n"

    # 3. 注入思考链 (CoT) 的超强 Prompt
    prompt = f"""你是一名高级网络架构师，正在主导诊断网络故障。你可以自由决定派发哪些任务给下属 Worker 排查。
【网络拓扑】
{state["lab_name"]}

【用户投诉】
{state["problem_info"]}

【全局巡检】
{state["inspector_result"]}

【成功排障经验】
{state.get("experience_result", "暂无经验")}

【历史排查总时间线】
这是你之前几轮的反思总结，不要重复测已经排除的故障！
{chr(10).join(history_reports) if history_reports else "暂无历史记录。"}

【刚刚完成的 Worker 排查反馈】
{current_feedback}
基于这些反馈决定下一步。

【当前场景所有可能的故障】
{relevant_faults}

🚨 【绝对禁区（已排除的故障黑名单）】
[{black_list_str}]
注意：你绝对、绝对不允许在这一轮中再次提出上述黑名单中的故障！如果你重复提出，将被系统立刻判定为重大失职！

【决策规范】
请你严格进行分步思考，并输出如下 JSON 格式：
{{
    // 第一步：反思。仔细阅读【刚刚完成的 Worker 排查反馈】，总结出哪些故障被排除了，哪些有了新发现。如果是第一轮，请写“启动初次排查，暂无反馈”。
    "round_summary": "从 WorkerXX 的 xx, 可以确定故障 xx; ...", 
    
    // 第二步：行动。若已有充分证据确诊，或无路可走，填 "finish"。若还需排查，填 "continue"。
    "action": "continue", 
    
    // 第三步：假设。仅在 continue 时填写，1~4 个你想让 Worker 并行去验证的假设。格式必须严格为 "故障标识 | 对应的模糊投诉表象" (绝对不要包含上一轮已经【排除】的故障！)
    "hypotheses": ["故障名1 | 表象1", "故障名2 | 表象2" ...], 
    
    // 第四步：经验指导。仅在 continue 时填写，从【成功排障经验】中为每一个 hypotheses 提取指导。数组长度必须对齐！
    "experiences": ["经验1", "经验2" ...], 
    
    // 第五步：最终结论。仅在 finish 时填写，输出最终确诊的故障和节点。
    "final_faults": {{"故障名1": ["节点名1", "节点名2" ...],
                      "故障名2": ["节点名1", "节点名2" ...] ...}} 
}}

"""
    # 重试 3 次
    llm = load_model(backend_model="qwen3.5-medium")
    max_retries = 3
    decision = {}
    for attempt in range(max_retries):
        try:
            res = await llm.ainvoke([HumanMessage(content=prompt)])
            clean_json = res.content.replace("```json", "").replace("```", "").strip()
            decision = json.loads(clean_json)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)
            else:
                decision = {"round_summary": "解析失败", "action": "continue", "hypotheses": [], "experiences": [], "final_faults": {}}

    print(f"🧠 [Supervisor 总结]: {decision.get('round_summary', '无')}")
    print(f"🎯 [Supervisor 决策]: {decision.get('action')} | 下发任务: {decision.get('hypotheses', [])}")
    
    # 组装返回给图状态的数据
    new_history = []
    if worker_results and decision.get("round_summary"):
        # 确保追加到 new_history 列表中
        new_history.append(f"[第 {iteration - 1} 轮总结]: {decision['round_summary']}")

    return {
        "iteration_count": iteration,
        "history_reports": new_history,  # 这里传入列表 []，结合 manage_history_reports 会安全相加
        "next_action": decision.get("action", "continue"),
        "hypotheses": decision.get("hypotheses", []),
        "experiences": decision.get("experiences", []),
        "final_faults": decision.get("final_faults", {}),
        "worker_results": "CLEAR"        # 这里传入字符串，触发 manage_worker_results 的清空逻辑
    }