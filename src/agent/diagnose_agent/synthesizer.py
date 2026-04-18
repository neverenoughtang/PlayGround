# src/agent/diagnose_agent/synthesizer.py
import json
from langchain_core.messages import HumanMessage
from utils.llm_models import load_model
from .state import DiagnoseState

async def synthesizer_node(state: DiagnoseState):
    """
    【聚合决策者】
    接收所有 Worker 的局部诊断结果，结合全局巡检信息，
    逻辑性地合成一份最终的复合故障清单。
    """
    print("\n" + "🧠 [Synthesizer] 正在汇总各路专家证据，合成最终诊断报告...")
    
    results = state.get("worker_results", [])
    if not results:
        print("⚠️ [Synthesizer] 未收到任何 Worker 的诊断结果。")
        return {"final_faults": {}}

    # 准备给 LLM 的上下文：包含巡检、假设和 Worker 的提交内容
    workers_info = ""
    for w in results:
        workers_info += f"- 专家ID: {w['worker_id']}\n"
        workers_info += f"  负责假设: {w['hypothesis']}\n"
        workers_info += f"  提交诊断: {json.dumps(w['submitted_faults'], ensure_ascii=False)}\n"
        workers_info += f"  排查发现: {w['trajectory_log'][-500:]} (注:仅展示末尾轨迹)\n\n"

    # 调用 Big 模型进行高级逻辑合成
    llm = load_model(backend_model="qwen3.5-big")
    
    prompt = f"""你是网络故障诊断系统的总架构师。
当前任务是根据多个并行排查专家的发现，合成一份最终的【复合故障清单】。

【全局上下文】
- 网络拓扑: {state['lab_name']}
- 全局巡检摘要: {state['inspector_result']}
- 用户原始投诉: {state['problem_info']}

【各专家排查结果】
{workers_info}

【工作要求】
1. 冲突处理：如果两个专家对同一个节点给出了矛盾的结论（例如一个说IP错，一个说网卡DOWN），请结合【全局巡检摘要】判断哪个更合理。
2. 重复合并：将不同专家发现的同类故障进行去重合并。
3. 逻辑验证：确保最终结论能解释【用户原始投诉】中的所有异常。
4. 输出格式：必须输出为 JSON 字典，格式为: {{"故障名称1": ["节点1", "节点2", ...], "故障名称2": ["节点1", "节点2", ...], ...}}。

请直接输出最终的 JSON 结果。
"""
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        # 清洗 JSON 字符串
        clean_json = res.content.replace("```json", "").replace("```", "").strip()
        final_faults = json.loads(clean_json)
        print(f"✅ [Synthesizer] 最终结论合成完毕: {final_faults}")
    except Exception as e:
        print(f"❌ [Synthesizer] 合成逻辑出错，执行退化合并方案: {e}")
        # 退化方案：简单的硬合并
        final_faults = {}
        for w in results:
            for fault, nodes in w["submitted_faults"].items():
                if fault not in final_faults: final_faults[fault] = []
                final_faults[fault].extend(nodes)
                final_faults[fault] = list(set(final_faults[fault]))

    return {"final_faults": final_faults}