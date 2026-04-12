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
# FRR 类故障测试套件配置 (混合参数测试)
# ==========================================
FRR_FAULT_SUITE = [
    # "路由器 r1，删除它到某个当前真实可达的目标业务网段的静态路由，让发往该网段的流量直接变成网络不可达",
    # "随机挑一台路由器，把某个真实业务网段改成 blackhole 路由，让经过该路由器转发到该网段的流量被静默丢弃",
    # "随机挑一台中间路由器，在 FORWARD 链上插入一条针对 ICMP 的 DROP 规则，让跨网段 Ping 全部失败，但其他 TCP 或 UDP 业务尽量保持不受影响",
    # "路由器 r2，依次强杀 zebra 和 bgpd 两个 FRR 守护进程，制造 FRR 服务整体宕机的故障",
    # "随机挑一台中间路由器，把 net.ipv4.ip_forward 设置为 0，关闭 Linux 内核三层转发能力，让经过它的跨网段业务全部中断",
    # "路由器r1，把某个已承载业务的三层接口地址改成错误的 IP 和掩码，并保持接口 up，制造网关地址错误导致的直连网段异常"
]

def run_all_frr_tests():
    lab_name = "static_routing" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: FRR类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(FRR_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(FRR_FAULT_SUITE)}]")
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
    run_all_frr_tests()