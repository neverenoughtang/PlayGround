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
# AI类故障测试套件配置 (混合参数测试)
# ==========================================
AI_FAULT_SUITE = [
    # "随机挑一台 ai_inference 场景中的算力节点，直接终止 python3 推理进程，制造 AI 推理进程崩溃故障",
    "随机挑一台 ai_inference 场景中的算力节点，使用 stress-ng 持续打满 CPU，例如启动 2 个或 4 个 worker 持续 300 秒，制造算力节点 CPU 满载故障",
    "随机挑一台 ai_inference 场景中的算力节点，使用 stress-ng 持续占用 90% 到 95% 内存并保持 300 秒，制造算力节点内存溢出故障",
    # "随机挑一台 ai_inference 场景中的算力节点，在 INPUT 链中插入一条针对 TCP 8000 端口的 DROP 规则，制造推理端口防火墙阻断故障",
    # "随机挑一台 ai_inference 场景中的中间转发节点，在 FORWARD 链中插入一条针对 TCP 流量的 REJECT --reject-with tcp-reset 规则，制造 AI 业务连接被异常重置的故障",
    # "随机挑一台 ai_inference 场景中的中间转发节点，在 FORWARD 链中插入一条针对 server_ip:8000 的 DROP 规则，制造算网隔离或跨层路由黑洞故障"
]
def run_all_bgp_tests():
    lab_name = "ai_inference" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: AI类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(AI_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(AI_FAULT_SUITE)}]")
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