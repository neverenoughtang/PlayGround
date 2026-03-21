import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector, HOST_INJECT_INPUT, LINK_INJECT_INPUT

# =====================================================================
# 具体故障测试逻辑 (基于 FaultInjector 调度，保留严格特征校验)
# =====================================================================

def _get_target_ip(lab_name: str) -> str:
    """辅助方法：从主机配置字典中动态获取当前场景的跨网段目标 IP"""
    return HOST_INJECT_INPUT[lab_name]["peer_ip_cross_subnet"]

def test_link_latency(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> 故障 1: 链路高延迟 (High Latency)")
    inj_pool.inject("inject_link_latency")
    time.sleep(1)
    
    dst_ip = _get_target_ip(cfg["lab"])
    target_host = cfg["host"]
    
    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 目标 {dst_ip} (发4包)...")
    ping_res = inj_pool.link_inj.api._run_cmd(target_host, f"ping -c 4 -W 2 {dst_ip}")
    print(f"[Ping 输出 (应观察到时间激增，time 约 500+ ms)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查主机 {target_host} 的 TC 排队规则 ...")
    agent_res = inj_pool.link_inj.api._run_cmd(target_host, "tc qdisc show")
    
    # 提取 NetEm 规则，避免大段无用输出
    netem_lines = [line for line in agent_res.split('\n') if 'netem' in line]
    print(f"[Agent 诊断输出 (提取 NetEm 规则)]:\n{netem_lines[0].strip() if netem_lines else agent_res.strip()}")
    
    if "time=" in ping_res:
        if "delay 500.0ms" in agent_res or "delay 500ms" in agent_res:
            print("✅ 表现特征与Agent识别成功: 成功捕获到内核级 netem 延迟规则！")
        else:
            print("❌ Agent识别失败: 未发现延迟注入规则")
    else:
        print("❌ 表现特征不符: Ping完全失败或无输出")


def test_link_loss(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> 故障 2: 链路高丢包 (Packet Loss)")
    inj_pool.inject("inject_link_loss")
    time.sleep(1)
    
    dst_ip = _get_target_ip(cfg["lab"])
    target_host = cfg["host"]
    
    print(f"\n[*] 表现特征观测: 从 {target_host} 快速 Ping 目标 {dst_ip} (发30包，降低随机性偏差)...")
    ping_res = inj_pool.link_inj.api._run_cmd(target_host, f"ping -c 30 -i 0.1 -W 1 {dst_ip}")
    
    loss_line = [line for line in ping_res.split('\n') if 'packet loss' in line]
    print(f"[Ping 输出 (应观察到 ~30% 左右的随机丢包)]:\n{loss_line[0] if loss_line else ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查主机 {target_host} 的 TC 排队规则 ...")
    agent_res = inj_pool.link_inj.api._run_cmd(target_host, "tc qdisc show")
    
    netem_lines = [line for line in agent_res.split('\n') if 'netem' in line]
    print(f"[Agent 诊断输出]:\n{netem_lines[0].strip() if netem_lines else agent_res.strip()}")
    
    if "loss 30" in agent_res:
        if "0% packet loss" not in (loss_line[0] if loss_line else ""):
             print("✅ 表现特征与Agent识别成功: 成功捕获到内核级 netem 丢包规则，且 Ping 表现出丢包！")
        else:
             print("⚠️ Agent识别成功，但 Ping 表现特征依然是 0% 丢包 (玄学运气极佳，所有包都躲过了丢弃)。")
    else:
        print("❌ Agent识别失败: 未发现丢包注入规则")


def test_link_jitter(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> 故障 3: 链路高抖动 (Jitter)")
    inj_pool.inject("inject_link_jitter")
    time.sleep(1)
    
    dst_ip = _get_target_ip(cfg["lab"])
    target_host = cfg["host"]
    
    print(f"\n[*] 表现特征观测: 从 {target_host} 快速 Ping 目标 {dst_ip} (发10包)...")
    ping_res = inj_pool.link_inj.api._run_cmd(target_host, f"ping -c 10 -i 0.2 -W 1 {dst_ip}")
    print(f"[Ping 输出 (应观察到 rtt mdev 极高，延迟忽高忽低)]:\n{ping_res.strip()[-150:]}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查主机 {target_host} 的 TC 排队规则 ...")
    agent_res = inj_pool.link_inj.api._run_cmd(target_host, "tc qdisc show")
    
    netem_lines = [line for line in agent_res.split('\n') if 'netem' in line]
    print(f"[Agent 诊断输出]:\n{netem_lines[0].strip() if netem_lines else agent_res.strip()}")
    
    if "100.0ms" in agent_res and ("80" in agent_res or "normal" in agent_res):
        print("✅ 表现特征与Agent识别成功: 成功捕获到内核级 netem 抖动(Jitter)与正态分布规则！")
    else:
        print("❌ Agent识别失败: 未发现抖动注入规则")


def test_link_bandwidth(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> 故障 4: 链路带宽限制 (Bandwidth Throttling)")
    inj_pool.inject("inject_link_bandwidth")
    time.sleep(1)
    
    dst_ip = _get_target_ip(cfg["lab"])
    target_host = cfg["host"]
    
    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 目标 {dst_ip} (发4包)...")
    ping_res = inj_pool.link_inj.api._run_cmd(target_host, f"ping -c 4 -W 1 {dst_ip}")
    print(f"[Ping 输出 (低频小包 Ping 通常不受带宽限制影响，连通性正常)]:\n{ping_res.strip()}")
    
    print(f"\n[*] Agent 诊断逻辑观测: 检查主机 {target_host} 的 TC 排队规则 ...")
    agent_res = inj_pool.link_inj.api._run_cmd(target_host, "tc qdisc show")
    
    netem_lines = [line for line in agent_res.split('\n') if 'rate' in line]
    print(f"[Agent 诊断输出 (提取 Rate 规则)]:\n{netem_lines[0].strip() if netem_lines else agent_res.strip()}")
    
    if "rate" in agent_res and ("1000" in agent_res or "1M" in agent_res):
        print("✅ 表现特征与Agent识别成功: 成功捕获到内核级 netem/tbf 带宽限速(Rate limit)规则！")
    else:
        print("❌ Agent识别失败: 未发现带宽限制规则")


if __name__ == "__main__":
    lab = "simple_bgp"

    # 执行测试
    run_scenario_tests(lab, [
        test_link_latency, 
        test_link_loss, 
        test_link_jitter, 
        test_link_bandwidth
    ], LINK_INJECT_INPUT)