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
# SDN类故障测试套件配置 (混合参数测试)
# ==========================================
SDN_FAULT_SUITE = [
    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 SDN 控制器节点，依次杀掉 ryu-manager 和 python 进程，制造控制器崩溃故障",

    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 OVS 交换机，先查出 bridge 名称，再删除该 bridge 的 controller 配置，制造 OVS 与控制器断连故障",

    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 OVS 交换机，先查出 bridge 名称，再注入一条 priority 65535 actions=drop 的流表，制造全局 DROP 流表故障",

    # 替换原 southbound_port_block，待测
    "随机挑一台 sdn_openflow 场景中的 OVS 交换机，先查出 bridge 名称，再把该 bridge 的 controller 地址改成错误的 tcp:192.168.254.254:6653，制造南向控制器地址错配故障",

    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 OVS 交换机，把 bridge 协议版本强制改成 OpenFlow10，制造南向协议错配故障",

    # 新增替换原 flow_rule_missing，待测
    "随机挑一台 sdn_openflow 场景中的 OVS 交换机，先查出 bridge 名称，再注入一条 priority 1000 actions=normal 的高优先级通配规则，制造流表规则覆盖故障",

    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 OVS 交换机，注入一条 in_port=1 actions=output:1 的高优先级流表，制造流表环路故障",

    # 已成功
    # "随机挑一台 sdn_openflow 场景中的 OVS 交换机，把 bridge 的 fail-mode 改成 secure，制造控制器失联后本地兜底转发失效的故障"
]

def run_all_bgp_tests():
    lab_name = "sdn_openflow" 
    
    print(f"\n{'='*70}")
    print(f"🧪 [开始自动化注入测试]: SDN类自然语言故障")
    print(f"📍 测试场景: {lab_name}")
    print(f"{'='*70}\n")
    
    for idx, fault_query in enumerate(SDN_FAULT_SUITE, 1):
        print(f"\n" + "🌟"*35)
        print(f"▶️  [执行用例 {idx}/{len(SDN_FAULT_SUITE)}]")
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