import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_bgp_shutdown(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: BGP 邻居管理性关闭 (BGP Neighbor Admin Shutdown)")
    inj.inject("inject_bgp_neighbor_shutdown")
    time.sleep(5) 
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的 BGP 邻居状态 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show ip bgp summary'")
    print(f"[Agent 诊断输出]:\n{agent_res.strip()}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if "Admin" in agent_res or "Idle" in agent_res:
            print("✅ 表现特征与Agent识别成功: Ping不通，且BGP邻居状态明确显示为 Idle / Admin Shutdown！")
        else:
            print("❌ Agent识别失败: 邻居状态不符合预期")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_bgp_withdraw(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: BGP 撤销网段宣告 (BGP Withdraw Network)")
    net = cfg["withdraw_net"] 
    inj.inject("inject_bgp_withdraw_route")
    time.sleep(5)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的运行配置 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show running-config'")
    print(f"[Agent 诊断输出 (配置截取)]:\n{agent_res[-400:].strip()}") 
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if f"network {net}" not in agent_res and "redistribute connected" not in agent_res:
            print(f"✅ 表现特征与Agent识别成功: Ping不通，且 BGP 配置中已彻底移除该网段的宣告与重分发！")
        else:
            print("❌ Agent识别失败: 配置中居然还有该网段的路由引入方式")
    else:
        print("❌ 表现特征不符: 还能Ping通")

def test_bgp_wrong_asn(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: BGP AS 号配置错误 (BGP Wrong Peer ASN)")
    inj.inject("inject_bgp_wrong_peer_asn")
    time.sleep(5)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的 BGP 邻居状态 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show ip bgp summary'")
    print(f"[Agent 诊断输出]:\n{agent_res.strip()}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if "Active" in agent_res or "Idle" in agent_res:
            state = "Active" if "Active" in agent_res else "Idle"
            print(f"✅ 表现特征与Agent识别成功: Ping不通，且 BGP 邻居状态卡在 {state} (因AS号不匹配无法 Established)！")
        else:
            print("❌ Agent识别失败: 邻居状态未体现故障")
    else:
        print("❌ 表现特征不符: 还能Ping通")

if __name__ == "__main__":
    run_scenario_tests("simple_bgp", [test_bgp_shutdown, test_bgp_withdraw, test_bgp_wrong_asn], SERVICE_INJECT_INPUT)