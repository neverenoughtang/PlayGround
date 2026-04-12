import sys
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../../"))
project_root = os.path.abspath(os.path.join(src_dir, ".."))
if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

from agent.test.agent_test_runner import run_injection_only_test

# 现在套件里不再是生硬的函数名，而是直接给大模型的自然语言指令
LINK_FAULT_SUITE = [
    # "在主机h1的对外链路上注入一次链路70%丢包故障",
    "给主机h2网卡加上500ms的链路延迟",
    # "帮我造一个网络延迟极度不稳定的抖动故障",
    # "把某个主机的网卡限速到 100kbps 造成拥塞"
]

def run_all_link_tests():
    lab_name = "static_routing" # 链路故障适合用静态路由拓扑测
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: 链路类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(LINK_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(LINK_FAULT_SUITE)}]")
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
    run_all_link_tests()