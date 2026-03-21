import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_rip_withdraw(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: RIP 撤销网络宣告 (RIP Withdraw Network)")
    inj.inject("inject_rip_withdraw_network")
    time.sleep(5)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出 (注: RIP失效定时器180s，连通性暂保)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查路由器 {cfg['router']} 的运行配置 ...")
    agent_res_conf = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show running-config'")
    
    if "[ERROR]" in agent_res_conf or "无输出" in agent_res_conf:
        print("❌ Agent识别失败: API 调用底层报错或节点不存在")
        return

    print(f"[Agent 诊断输出 (RIP 运行配置截取)]:\n{agent_res_conf[-300:].strip()}")
    has_network = f"network {cfg['withdraw_net']}" in agent_res_conf
    has_redist = "redistribute connected" in agent_res_conf
    
    if not has_network and not has_redist:
        print(f"✅ 表现特征与Agent识别成功: Agent 敏锐发现 {cfg['withdraw_net']} 的宣告与重分发已被彻底撤销！")
    else:
        print("❌ Agent识别失败: 配置中依然存在引入信息")

def test_rip_passive(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: RIP 接口静默 (RIP Passive Interface)")
    inj.inject("inject_rip_passive_interface")
    time.sleep(3)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出 (存在 0% 丢包的欺骗性)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查接口状态与配置 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show running-config'")
    passive_lines = [line for line in agent_res.split('\n') if 'passive-interface' in line]
    print(f"[Agent 诊断输出]:\n{passive_lines[0].strip() if passive_lines else '(未找到 passive 标记)'}")
    
    if f"passive-interface {cfg['passive_iface']}" in agent_res:
        print(f"✅ 表现特征与Agent识别成功: 成功发现接口 {cfg['passive_iface']} 被恶意设置为被动模式！")
    else:
        print("❌ Agent识别失败: 未发现 Passive 接口配置")

def test_rip_version(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: RIP 版本不匹配 (RIP Version Mismatch)")
    inj.inject("inject_rip_version_mismatch")
    time.sleep(3)
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 跨网段目标 {cfg['dst_ip']} (发4包)...")
    ping_res = inj.service_inj.frr._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {cfg['dst_ip']}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查 RIP 版本配置 ...")
    agent_res = inj.service_inj.frr._run_cmd(cfg['router'], "vtysh -c 'show running-config'")
    version_lines = [line for line in agent_res.split('\n') if 'version 1' in line]
    print(f"[Agent 诊断输出]:\n{version_lines[0].strip() if version_lines else '(无 version 1 配置)'}")
    
    if "version 1" in agent_res:
        print("✅ 表现特征与Agent识别成功: 成功发现接口被非法降级为 RIPv1！")
    else:
        print("❌ Agent识别失败: 未发现 RIP 版本降级配置")


if __name__ == "__main__":
    run_scenario_tests("rip_internet", [test_rip_withdraw, test_rip_passive, test_rip_version], SERVICE_INJECT_INPUT)