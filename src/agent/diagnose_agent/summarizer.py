# src/agent/diagnose_agent/summarizer.py
import json

async def summarizer_node(state: dict):
    """
    【最终结算与入库节点】
    计算 Argus MAS 系统的综合性能指标，并打印炫酷的全局战报。
    """
    print("\n" + "="*70)
    print("📝 [Summarizer] 诊断已结束，正在结算全域评测指标...")
    print("="*70)
    
    # ---------------------------------------------------------
    # 1. 极致安全的资源指标提取 (防 KeyError 与 None)
    # ---------------------------------------------------------
    total_tool_calls = state.get("global_tool_calls") or 0
    token_dict = state.get("global_token_usage") or {}
    
    total_tokens = token_dict.get("total_tokens") or 0
    in_tokens = token_dict.get("input_tokens") or 0
    out_tokens = token_dict.get("output_tokens") or 0

    # ---------------------------------------------------------
    # 2. 精准计算 Precision 与 Recall
    # ---------------------------------------------------------
    expected_faults = state.get("expected_faults") or {}
    final_faults = state.get("final_faults") or {}

    # 展平预期故障集合 (例如 {"link_loss": ["h1", "h2"]} -> {"link_loss|h1", "link_loss|h2"})
    expected_set = set()
    for f, nodes in expected_faults.items():
        if isinstance(nodes, list):
            for n in nodes: expected_set.add(f"{f}|{n}")
        else:
            expected_set.add(f"{f}|{nodes}")
            
    # 展平 Agent 诊断出的故障集合
    pred_set = set()
    for f, nodes in final_faults.items():
        if isinstance(nodes, list):
            for n in nodes: pred_set.add(f"{f}|{n}")
        else:
            pred_set.add(f"{f}|{nodes}")
            
    true_positives = len(expected_set & pred_set)
    
    # 注意：计算百分比时，* 100.0 必须放在除法结果的外面
    precision = (true_positives / len(pred_set) * 100.0) if pred_set else 0.0
    recall = (true_positives / len(expected_set) * 100.0) if expected_set else 0.0

    # ---------------------------------------------------------
    # 3. 经验入库动作预留区
    # ---------------------------------------------------------
    # 在这里可以写入你把成功经验传入 MySQL 或其他向量库的逻辑
    # 我们这里仅仅提取最终的字典准备打印
    extracted_experience = json.dumps(final_faults, ensure_ascii=False)

    # ---------------------------------------------------------
    # 4. 全量、透明、霸气的控制台战报打印
    # ---------------------------------------------------------
    print("\n" + "★"*70)
    print(" "*23 + "🏆 Argus 诊断全局战报 🏆")
    print("★"*70)
    
    print(f"🎯 【评测核心指标】")
    # 保留两位小数，正常计算会输出例如 50.00% 或 100.00%
    print(f"   - 精确率 (Precision) : {precision:.2f}%")
    print(f"   - 召回率 (Recall)    : {recall:.2f}%")
    
    print(f"\n📊 【资源消耗账单】")
    print(f"   - 工具探测总计       : {total_tool_calls} 次")
    # 加入千位分隔符，大数字更易读 (如 1,234,567 tokens)
    print(f"   - Token 算力消耗     : {total_tokens:,} tokens")
    print(f"       └─ 接收 (Input): {in_tokens:,} | 生成 (Output): {out_tokens:,}")
    
    print(f"\n🔬 【断案矩阵比对】")
    print(f"   - 真实埋点 (Expected): {json.dumps(expected_faults, ensure_ascii=False)}")
    print(f"   - 兵团诊断 (Predicted): {json.dumps(final_faults, ensure_ascii=False)}")
    
    print(f"\n💾 【经验提取备存】")
    print(f"   {extracted_experience}")
    print("★"*70 + "\n")

    # 5. 更新图状态
    return {
        "precision": precision,
        "recall": recall,
        # 你可以根据你的逻辑选择是否将最终结论写入 trajectory 给 Judge
        "trajectory": f"诊断完成，最终确诊故障：{extracted_experience}"
    }