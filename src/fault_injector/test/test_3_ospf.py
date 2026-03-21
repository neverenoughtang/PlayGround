import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_ospf_passive(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: OSPF 接口静默 (OSPF Passive Interface)")
    inj.inject("inject_ospf_passive_interface")
    time.sleep(3)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出 (流量可能短暂中断后切换至备用路径)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查接口 {cfg['passive_iface']} OSPF 状态 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], f"vtysh -c 'show ip ospf interface {cfg['passive_iface']}'")
    
    passive_line = [line for line in agent_res.split('\n') if 'No Hellos' in line or 'Passive' in line]
    print(f"[Agent 诊断输出 (状态提取)]:\n{passive_line[0].strip() if passive_line else agent_res[:150]}")
    
    if "No Hellos" in agent_res or "Passive" in agent_res:
        print("✅ 表现特征与Agent识别成功: 接口已被成功标记为 Passive (No Hellos)，邻居即将或已经断开！")
    else:
        print("❌ Agent识别失败: 接口状态未体现 Passive 故障")

def test_ospf_cost(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: OSPF 接口开销突增 (OSPF Cost Spike)")
    inj.inject("inject_ospf_cost_spike")
    time.sleep(3)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出 (流量发生次优路径绕路，连通性不中断)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查接口 {cfg['passive_iface']} OSPF Cost 值 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], f"vtysh -c 'show ip ospf interface {cfg['passive_iface']}'")
    
    cost_line = [line for line in agent_res.split('\n') if 'Cost' in line]
    print(f"[Agent 诊断输出 (Cost 提取)]:\n{cost_line[0].strip() if cost_line else agent_res[:100]}")
    
    if "Cost is 65000" in agent_res or "65000" in agent_res:
        print("✅ 表现特征与Agent识别成功: 接口 OSPF Cost 已飙升至 65000！")
    else:
        print("❌ Agent识别失败: 接口 Cost 值未按预期突增")

def test_ospf_crash(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: OSPF 进程崩溃 (OSPF Daemon Crash)")
    inj.inject("inject_ospf_daemon_crash")
    time.sleep(3)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出 (完美展现 OSPF 断网与瞬间自愈的过程)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的 ospfd 进程状态 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "sh -c 'ps | grep [o]spfd'")
    print(f"[Agent 诊断输出]:\n{agent_res.strip() if agent_res.strip() else '(无任何进程输出)'}")
    
    if not agent_res.strip() or "无输出" in agent_res:
        print("✅ 表现特征与Agent识别成功: 核心守护进程 ospfd 已被彻底杀死 (网络已通过高可用路径自愈)！")
    else:
        print("❌ Agent识别失败: ospfd 进程居然还在运行")


if __name__ == "__main__":
    run_scenario_tests("ospf_enterprise", [test_ospf_passive, test_ospf_cost, test_ospf_crash], SERVICE_INJECT_INPUT)