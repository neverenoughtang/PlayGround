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
# OSPF类故障测试套件配置 (混合参数测试)
# ==========================================
OSPF_FAULT_SUITE = [
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，先查看当前 OSPF 邻居，从中选一个正在建立邻居关系的互联接口，把该接口配置为 passive-interface，制造 OSPF 接口静默导致邻居消失的故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，把某个骨干或核心互联接口的 OSPF cost 异常抬高到 65000，制造明显的路径切换和重收敛故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，直接强杀 ospfd 守护进程，制造单点 OSPF 进程崩溃的故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，在 INPUT 链插入一条针对协议号 89 的 DROP 规则，等待邻居超时后制造 ACL 阻断 OSPF 报文导致邻居消失的故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，把某个当前正在建立邻居关系的互联接口 hello-interval 改成 99 秒，制造 Hello 定时器错配导致邻居异常或无法维持的故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，从它当前的 OSPF network 宣告中挑一个核心互联网段，错误地改宣告到 area 99，制造 OSPF 区域错配故障",
    "随机挑一台 ospf_enterprise 场景中的 OSPF 路由器，在某个互联接口上开启 message-digest 认证并配置错误密钥 wrongkey123，制造 OSPF 接口认证错配导致邻居中断的故障"
]

def run_all_bgp_tests():
    lab_name = "ospf_enterprise" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: OSPF类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(OSPF_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(OSPF_FAULT_SUITE)}]")
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