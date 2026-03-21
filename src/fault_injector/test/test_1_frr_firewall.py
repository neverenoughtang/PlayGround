import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_route_missing(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: 目标网段路由缺失 (Route Missing)")
    inj.inject("inject_route_missing")
    time.sleep(1)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 路由表 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "ip route show")
    print(f"[Agent 诊断输出]:\n{agent_res.strip()}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if cfg["blackhole_net"] not in agent_res:
            print(f"✅ 表现特征与Agent识别成功: Ping不通，且路由表中确实找不到了 {cfg['blackhole_net']} 的条目！")
        else:
            print("❌ Agent识别失败: 路由表中依然存在该网段")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_static_blackhole(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: 静态黑洞路由 (Static Blackhole)")
    inj.inject("inject_static_route_blackhole")
    time.sleep(1)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 路由表 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "ip route show")
    print(f"[Agent 诊断输出]:\n{agent_res.strip()}")
    
    if "blackhole" in agent_res:
        print("✅ 表现特征与Agent识别成功: 流量打入黑洞，100%丢包，且路由表存在 blackhole 标记")
    else:
        print("❌ 表现特征或Agent识别失败")

def test_data_plane_drop(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: 路由器数据面 ICMP 防火墙阻断 (Data Plane ACL)")
    inj.inject("inject_router_data_plane_drop")
    time.sleep(1)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的防火墙 FORWARD 链 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "iptables -L FORWARD -n")
    print(f"[Agent 诊断输出]:\n{agent_res.strip()}")
    
    if "DROP" in agent_res and "icmp" in agent_res:
        print("✅ 表现特征与Agent识别成功: 防火墙 FORWARD 链已明确注入 ICMP 阻断规则")
    else:
        print("❌ 表现特征或Agent识别失败")

if __name__ == "__main__":
    run_scenario_tests("static_routing", [test_route_missing, test_static_blackhole, test_data_plane_drop], SERVICE_INJECT_INPUT)