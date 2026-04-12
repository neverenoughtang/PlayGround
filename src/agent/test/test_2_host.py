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
# 主机类故障测试套件配置 (混合参数测试)
# ==========================================
HOST_FAULT_SUITE = [
    # 1. IP 配置错误 (带参数：明确指定机器和错误 IP)
    "帮我把主机 h1 的对外网卡 IP 错误配置为 100.99.88.77/24",
    # 2. 默认路由缺失 (无参数：要求 Agent 自行去拓扑里随便挑一台主机删路由)
    "随便挑一台主机，把它的默认网关删掉，让它无法跨网段通信",
    # 3. ARP 缓存投毒 (带参数：指定目标机和虚假 MAC)
    "在主机 h2 上进行 ARP 投毒，把网关的 IP 强制绑定到假 MAC 地址 aa:bb:cc:dd:ee:ff",
    # 4. 接口宕机 (无参数：模糊指令)
    "模拟一根物理网线断开，帮我把某台主机的网卡给 down 掉",
    # 5. DNS 配置错误 (带参数)
    "把主机 h1 的 DNS 服务器篡改成无效的 0.1.2.3，制造域名解析失败",
    # 6. CPU 资源满载 (无参数)
    "找个节点，跑满它的 CPU，让机器处于严重卡顿状态", # 未完成
    # 7. 主机静态路由错误 (带参数：制造路由黑洞)
    "给主机 h2 加一条静态路由错误，让它发往 8.8.8.0/24 网段的流量全部走不存在的网关 192.168.1.99", 
    # 8. 子网掩码错误 (无参数)
    "制造一个子网掩码配错的故障，比如把正常网卡改成极小的 /30 掩码",
    # 9. 主机端口耗尽 (无参数)
    "把某个主机的本地临时端口范围限制成只有 1 个，制造端口耗尽拒绝服务",
]

def run_all_host_tests():
    # 主机类故障最适合在纯静态路由场景下测，排除动态路由协议的干扰
    lab_name = "static_routing" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: 主机类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(HOST_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(HOST_FAULT_SUITE)}]")
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
    run_all_host_tests()