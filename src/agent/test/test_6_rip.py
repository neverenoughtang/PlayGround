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
# RIP类故障测试套件配置 (混合参数测试)
# ==========================================
RIP_FAULT_SUITE = [
    # 稳：仅依赖配置是否写入，容易成功
    # "随机挑一台 rip_internet 场景中的 RIP 路由器，把某个与 RIP 邻居相连的接口配置为 passive-interface，制造 RIP 接口静默导致对外不再发送更新的故障",

    # 不稳：对端路由不一定短时间变化，保留测试
    "随机挑一台 rip_internet 场景中的 RIP 路由器，先创建 access-list 99 deny any，再把 distribute-list 99 out 绑定到 RIP 进程，制造 RIP 路由过滤导致对端学不到路由的故障",

    # 不稳：offset-list 写入稳定，但路由表现不一定立刻明显，保留测试
    "随机挑一台 rip_internet 场景中的 RIP 路由器，先创建 access-list 98 permit any，再配置 offset-list 98 out 15，制造 RIP 度量值被异常抬高到接近不可达的故障",

    # 不稳：ACL 一定能打上，但 RIP 路由老化较慢，表象存在延迟，保留测试
    "随机挑一台 rip_internet 场景中的 RIP 路由器，在 INPUT 链插入一条针对 UDP 520 端口的 DROP 规则，制造 ACL 阻断 RIP 更新报文的故障",

    # 稳：版本错配+BadPackets 很容易观测
    # "随机挑一台 rip_internet 场景中的 RIP 路由器，把 RIP 版本强制改成 version 1，如果全网默认是 version 2，则制造稳定的 RIP 版本错配故障",

    # 稳：状态和配置都能直接看到
    # "随机挑一台 rip_internet 场景中的 RIP 路由器，把 timers basic 改成 999 999 999，制造 RIP 更新、超时和垃圾回收都极慢的计时器篡改故障",

    # 稳：配置变化和业务中断都明显
    # "随机挑一台 rip_internet 场景中的 RIP 路由器，撤销某个当前正在通过 RIP 发布的 network 宣告，制造该业务网段从 RIP 域中消失的故障"
]

def run_all_bgp_tests():
    lab_name = "rip_internet" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: RIP类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(RIP_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(RIP_FAULT_SUITE)}]")
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