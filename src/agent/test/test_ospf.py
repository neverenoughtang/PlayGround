import sys
import os
import time

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../../"))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 导入底层组件与测试执行器
from fault_injector.fault_inject_pool import SERVICE_INJECT_INPUT
# 注意：确保你的 agent_test_runner.py 中 run_agent_test_case 函数可以被导入
from agent.test.agent_test_runner import run_agent_test_case

# ==========================================
# 主机故障测试套件配置
# ==========================================
# 格式: (故障注入方法名, 期望的Root Cause字符串)
OSPF_FAULT_SUITE = [
    ("inject_ospf_passive_interface", "ospf_passive_interface"),
    ("inject_ospf_cost_spike", "ospf_cost_spike"),
    ("inject_ospf_daemon_crash", "ospf_daemon_crash")
]

def run_all_link_tests():
    """
    顺序运行所有 OSPF 相关的网络故障智能体诊断测试
    """
    # 选择一个基础场景，如 static_routing
    lab_name = "ospf_enterprise"
    
    # 检查当前 lab 是否在 HOST_INJECT_INPUT 配置中
    if lab_name not in SERVICE_INJECT_INPUT:
        print(f"❌ 找不到场景 {lab_name} 的故障注入参数配置。")
        return

    cfg = SERVICE_INJECT_INPUT[lab_name]
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化测试套件]: OSPF 类故障 (ospf Faults)")
    print(f"📍 测试场景: {lab_name}")
    print(f"📝 包含用例: {len(OSPF_FAULT_SUITE)} 个")
    print(f"{'='*70}\n")
    
    # 记录整体耗时和通过情况
    start_time = time.time()
    
    for idx, (fault_name, expected_root_cause) in enumerate(OSPF_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(OSPF_FAULT_SUITE)}]: {fault_name}")
        print("🌟"*35)
        
        try:
            # 调用你写好的端到端跑测函数
            run_agent_test_case(
                lab_name=lab_name,
                fault_name=fault_name,
                expected_root_cause=expected_root_cause,
                cfg=cfg
            )
        except Exception as e:
            print(f"\n❌ 用例 {fault_name} 在执行流中发生崩溃: {e}")
            
        print(f"\n⏳ 缓冲 3 秒，准备进入下一个用例...\n")
        time.sleep(3)
        
    total_time = time.time() - start_time
    minutes = int(total_time // 60)
    seconds = int(total_time % 60)
    
    print(f"\n{'='*70}")
    print(f"🎉 [自动化测试套件执行完毕]")
    print(f"⏱️  总耗时: {minutes} 分 {seconds} 秒")
    print(f"请向上翻阅日志查看每一个用例的具体 Agent 诊断过程和 ✅❌ 结果。")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    # 运行测试套件前，确认环境变量或 API key 已配置
    run_all_link_tests()