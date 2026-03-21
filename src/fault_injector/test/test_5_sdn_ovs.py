import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_ryu_crash(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: SDN 控制器进程崩溃 (Ryu Controller Crash)")
    inj.inject("inject_sdn_controller_crash")
    time.sleep(2)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.sdn._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查控制器 {cfg['controller']} 端口状态 ...")
    agent_res = inj.service_inj.sdn._run_cmd(cfg['controller'], "sh -c 'netstat -tulnp | grep 6653'")
    print(f"[Agent 诊断输出]:\n{agent_res.strip() if agent_res.strip() else '(无任何端口监听)'}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if not agent_res.strip() or "无输出" in agent_res:
            print("✅ 表现特征与Agent识别成功: 监听 OpenFlow 的 6653 端口已彻底消失，控制器瘫痪！")
        else:
            print("❌ Agent识别失败: 控制器端口依然在监听")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_ovs_disconnect(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: OVS 断开控制器连接 (OVS Disconnect Controller)")
    inj.inject("inject_ovs_disconnect_controller")
    time.sleep(2)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.ovs._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查交换机 {cfg['switch']} OVS 连接状态 ...")
    agent_res = inj.service_inj.ovs._run_cmd(cfg['switch'], "ovs-vsctl show")
    print(f"[Agent 诊断输出 (配置截取)]:\n{agent_res.strip()[:300]}...\n")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if "is_connected: true" not in agent_res:
            print("✅ 表现特征与Agent识别成功: OVS 状态中找不到 is_connected: true，控制面失联！")
        else:
            print("❌ Agent识别失败: 居然还连着控制器")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_ovs_drop(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: OVS 注入全局 DROP 流表 (OVS Global Drop Flow)")
    inj.inject("inject_ovs_global_drop_flow")
    time.sleep(2)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.ovs._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 审计交换机 {cfg['switch']} 流表 ...")
    agent_res = inj.service_inj.ovs._run_cmd(cfg['switch'], "sh -c 'br=$(ovs-vsctl list-br | head -n 1); ovs-ofctl dump-flows $br'")
    
    drop_lines = [line for line in agent_res.split('\n') if 'actions=drop' in line]
    print(f"[Agent 诊断输出]:\n{drop_lines[0].strip() if drop_lines else '(未找到 drop 流表)'}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if drop_lines and "priority=65535" in drop_lines[0]:
            print("✅ 表现特征与Agent识别成功: 成功在 OVS 中捕获到最高优先级 (65535) DROP 流表！")
        else:
            print("❌ Agent识别失败: 未能捕获到高优先级 DROP 流表")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

if __name__ == "__main__":
    run_scenario_tests("sdn_openflow", [test_ryu_crash, test_ovs_disconnect, test_ovs_drop], SERVICE_INJECT_INPUT)