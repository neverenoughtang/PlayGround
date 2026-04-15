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
# BGP类故障测试套件配置 (混合参数测试)
# ==========================================
BGP_FAULT_SUITE = [
    # "随机挑一台 simple_bgp 场景中的 BGP 路由器，把它与某个已建立会话的邻居执行管理性 shutdown，直接制造 BGP 邻居被手动关闭的故障",
    # "随机挑一台 simple_bgp 场景中的 BGP 路由器，撤销对某个当前正在发布的业务网段的 network 宣告，并同时取消 redistribute connected，制造路由撤销导致的前缀消失故障",
    # "随机挑一台 simple_bgp 场景中的 BGP 路由器，把某个邻居的 remote-as 改成一个错误但合理的 ASN，例如 65099，制造邻居 AS 号配置错误导致的会话无法建立",
    "随机挑一台参与 BGP 建邻的路由器，在 INPUT 链中插入一条针对 TCP 179 端口的 DROP 规则，制造 ACL 阻断 BGP 控制流量的故障",
    "随机挑一台存在多条 BGP 入方向路径可选的路由器，创建 route-map 并把某个邻居入方向的 local-preference 异常抬高到 999，制造路径偏好被错误操控的故障",
    "随机挑一台对外发布路由的 BGP 路由器，创建 route-map 并把某个邻居出方向的 MED 异常抬高到 9999，制造对端入口选择异常偏移的故障"
]

def run_all_bgp_tests():
    lab_name = "simple_bgp" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: BGP类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(BGP_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(BGP_FAULT_SUITE)}]")
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