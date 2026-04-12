import os
import sys

# ==========================================
# 环境锁：必须放在第一行！彻底屏蔽大模型库的啰嗦输出
# ==========================================
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

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
from agent.test.agent_test_runner import run_injection_only_test

# ==========================================
# P4类故障测试套件配置 (混合参数测试)
# ==========================================
P4_FAULT_SUITE = [
    # 已成功
    # "随机挑一台 p4_star 场景中的 P4 交换机，直接强杀 simple_switch 进程，制造 BMv2 引擎崩溃导致整台交换机数据平面不可用的故障",

    # 修复后待测
    "随机挑一台 p4_star 场景中的 P4 交换机，先查出某个目标 IP 对应表项的 handle，删除原表项后再为该目标 IP 重建一条 MyIngress.drop 表项，制造表项级 DROP 动作注入故障",

    # 已成功
    # "随机挑一台 p4_star 场景中的 P4 交换机，先查出某个目标 IP 对应表项的 handle，再把转发动作改成错误的 MAC 和异常 egress 端口 99，制造 P4 错误转发故障",

    # 已成功
    # "随机挑一台 p4_star 场景中的 P4 交换机，先查出某个目标 IP 对应表项的 handle，再直接删除该表项，制造 P4 表项缺失故障",

    # 已成功
    # "随机挑一台 p4_star 场景中的 P4 交换机，把关键转发表的默认动作改成 MyIngress.drop，制造默认动作级别的全局未命中丢包故障"
]

def run_all_bgp_tests():
    lab_name = "p4_star" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: P4类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(P4_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(P4_FAULT_SUITE)}]")
        print("🌟"*35)
        
        try:
            run_injection_only_test(
                lab_name=lab_name,
                fault_query=fault_query
            )
        except Exception as e:
            print(f"\n❌ 用例执行崩溃: {e}")
            
        print(f"\n⏳ 缓冲 3 秒，准备进入下一个用例...\n")
        time.sleep(3)
        
    print(f"\n🎉 [自动化注入测试执行完毕]")

if __name__ == "__main__":
    run_all_bgp_tests()