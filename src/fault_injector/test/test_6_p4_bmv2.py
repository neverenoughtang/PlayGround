import socket
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, SERVICE_INJECT_INPUT

def test_bmv2_crash(inj: FaultInjector, cfg):
    print("\n>>> 故障 1: BMv2 P4 引擎崩溃 (BMv2 Process Crash)")
    inj.inject("inject_bmv2_process_crash")
    time.sleep(2)
    
    dst_ip = cfg["drop_ip"].split("/")[0]
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {dst_ip} (发4包)...")
    ping_res = inj.service_inj.bmv2._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {dst_ip}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查交换机 {cfg['switch']} simple_switch 进程状态 ...")
    agent_res = inj.service_inj.bmv2._run_cmd(cfg['switch'], "sh -c 'ps | grep [s]imple_switch'")
    print(f"[Agent 诊断输出]:\n{agent_res.strip() if agent_res.strip() else '(无任何进程输出)'}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if not agent_res.strip() or "无输出" in agent_res:
            print("✅ 表现特征与Agent识别成功: 核心引擎 simple_switch 已彻底消失！")
        else:
            print("❌ Agent识别失败: 进程依然存活")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_p4_table_drop(inj: FaultInjector, cfg):
    print("\n>>> 故障 2: P4 表项级 DROP 动作注入 (P4 Table Drop)")
    inj.inject("inject_p4_table_drop")
    time.sleep(2)
    
    dst_ip = cfg["drop_ip"].split("/")[0]
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {dst_ip} (发4包)...")
    ping_res = inj.service_inj.bmv2._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {dst_ip}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 提取并审计 {cfg['table']} 流表 ...")
    agent_res = inj.service_inj.bmv2._run_cmd(cfg['switch'], f"sh -c 'echo \"table_dump {cfg['table']}\" | simple_switch_CLI'")
    
    ip_hex = socket.inet_aton(dst_ip).hex()
    lines = agent_res.split('\n')
    target_block = []
    for i, line in enumerate(lines):
        if ip_hex in line:
            target_block = lines[max(0, i-2):i+2]
            break
            
    print(f"[Agent 诊断输出 (流表审计提取)]:\n{chr(10).join(target_block)}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        if "MyIngress.drop" in agent_res:
            print("✅ 表现特征与Agent识别成功: 在查表中精准捕获到目标 IP 的 MyIngress.drop 动作项！")
        else:
            print("❌ Agent识别失败: 未发现 Drop 流表项")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")

def test_p4_wrong_port(inj: FaultInjector, cfg):
    print("\n>>> 故障 3: P4 错误转发动作注入 (P4 Wrong Forwarding Port)")
    inj.inject("inject_p4_wrong_forwarding")
    time.sleep(2)
    
    dst_ip = cfg["drop_ip"].split("/")[0]
    
    print(f"\n[*] 表现特征观测: 从 {cfg['host_src']} Ping 目标 {dst_ip} (发4包)...")
    ping_res = inj.service_inj.bmv2._run_cmd(cfg['host_src'], f"ping -c 4 -W 1 {dst_ip}")
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 提取并审计 {cfg['table']} 流表 ...")
    agent_res = inj.service_inj.bmv2._run_cmd(cfg['switch'], f"sh -c 'echo \"table_dump {cfg['table']}\" | simple_switch_CLI'")
    
    ip_hex = socket.inet_aton(dst_ip).hex()
    lines = agent_res.split('\n')
    target_block = []
    for i, line in enumerate(lines):
        if ip_hex in line:
            target_block = lines[max(0, i-2):i+2]
            break
            
    print(f"[Agent 诊断输出 (流表审计提取)]:\n{chr(10).join(target_block)}")
    
    wrong_port_int = int(cfg["wrong_port"])
    wrong_port_hex = hex(wrong_port_int)[2:] 
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        target_text = "\n".join(target_block)
        if (str(wrong_port_int) in target_text or wrong_port_hex in target_text) and "MyIngress.ipv4_forward" in target_text:
            print(f"✅ 表现特征与Agent识别成功: 成功发现发往目标 IP 的出端口被篡改为无效端口 {cfg['wrong_port']}！")
        else:
            print("❌ Agent识别失败: 未在对应表项中发现错误端口")
    else:
        print("❌ 表现特征不符: 居然还能Ping通")


if __name__ == "__main__":
    run_scenario_tests("p4_star", [test_bmv2_crash, test_p4_table_drop, test_p4_wrong_port], SERVICE_INJECT_INPUT)  