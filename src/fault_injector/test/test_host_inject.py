import sys
import time
from base_test_runner import run_scenario_tests
from fault_inject_pool import FaultInjector

# =====================================================================
# 具体故障测试逻辑 (基于 FaultInjector 调度，保留严格特征校验)
# =====================================================================

def test_interface_down(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (1) 测试: 接口物理关闭 (Interface Down)")
    # 使用统一接口注入故障，参数由 inj_pool 内部自动路由
    inj_pool.inject("inject_interface_down")
    time.sleep(1)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]
    iface = cfg["iface"]

    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 同网段主机 {h2_ip} (发4包)...")
    ping_res = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        print("✅ 表现特征符合: 100% packet loss 或 Network is unreachable")
    else:
        print("❌ 表现特征不符")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} 物理网卡状态 ...")
    link_res = inj_pool.host_inj.api._run_cmd(target_host, f"ip link show {iface}")
    print(f"[Agent 诊断输出 (ip link)]:\n{link_res.strip()}")
    
    if "DOWN" in link_res and "UP,LOWER_UP" not in link_res:
        print("✅ Agent 识别成功: 网卡状态包含 DOWN 且没有 UP,LOWER_UP 标识")
    else:
        print("❌ Agent 识别失败")


def test_ip_misconfig(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (2) 测试: IP 地址配置错误 (IP Misconfig)")
    inj_pool.inject("inject_ip_misconfig")
    time.sleep(1)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]
    iface = cfg["iface"]
    wrong_ip = cfg["wrong_ip"]

    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 同网段主机 {h2_ip} (发4包)...")
    ping_res = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    if "100% packet loss" in ping_res or "unreachable" in ping_res.lower():
        print("✅ 表现特征符合: 100% packet loss 或 Network is unreachable")
    else:
        print("❌ 表现特征不符")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} IP 地址 ...")
    addr_res = inj_pool.host_inj.api._run_cmd(target_host, f"ip addr show {iface}")
    print(f"[Agent 诊断输出 (ip addr)]:\n{addr_res.strip()}")
    
    if wrong_ip.split('/')[0] in addr_res:
        print(f"✅ Agent 识别成功: 发现主机的 IP 变成了莫名其妙的网段 ({wrong_ip})")
    else:
        print("❌ Agent 识别失败")


def test_default_route_missing(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (3) 测试: 默认路由缺失 (Default Route Missing)")
    inj_pool.inject("inject_default_route_missing")
    time.sleep(1)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]
    h4_ip = cfg["peer_ip_cross_subnet"]
    iface = cfg["iface"]

    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 同网段 ({h2_ip}) 与跨网段 ({h4_ip})...")
    ping_same = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    ping_cross = inj_pool.host_inj.api.linux_ping(target_host, h4_ip, count=4)
    print(f"[Ping 同网段输出]:\n{ping_same.strip()}\n")
    print(f"[Ping 跨网段输出]:\n{ping_cross.strip()}")
    
    if ("0% packet loss" in ping_same) and ("unreachable" in ping_cross.lower() or "100% packet loss" in ping_cross):
        print("✅ 表现特征符合: 同网段通畅，跨网段直接报 Network is unreachable 或 100% 丢包")
    else:
        print("❌ 表现特征不符")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} 路由表 ...")
    route_res = inj_pool.host_inj.api._run_cmd(target_host, "ip route show")
    print(f"[Agent 诊断输出 (ip route)]:\n{route_res.strip()}")
    
    if "default via" not in route_res and iface in route_res:
        print("✅ Agent 识别成功: 路由表里有局部路由，但没有 default via (默认网关丢失)")
    else:
        print("❌ Agent 识别失败")


def test_arp_poisoning(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (4) 测试: ARP 缓存投毒 (ARP Poisoning)")
    inj_pool.inject("inject_arp_poisoning")
    time.sleep(1)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]
    fake_mac = cfg["wrong_mac"]

    print(f"\n[*] 表现特征观测: 从 {target_host} Ping 目标主机 {h2_ip} (发4包)...")
    ping_res = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    print(f"[Ping 输出]:\n{ping_res.strip()}")
    
    if "100% packet loss" in ping_res:
        print("✅ 表现特征符合: 100% packet loss (发包无回应)")
    else:
        print("❌ 表现特征不符")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} ARP 表 ...")
    arp_res = inj_pool.host_inj.api._run_cmd(target_host, "ip neigh show")
    print(f"[Agent 诊断输出 (ip neigh)]:\n{arp_res.strip()}")
    
    if fake_mac in arp_res:
        print(f"✅ Agent 识别成功: 发现目标 IP 对应的 MAC 变成了错误地址 ({fake_mac})")
    else:
        print("❌ Agent 识别失败")


def test_dns_error(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (5) 测试: DNS 配置错误 (DNS Error)")
    inj_pool.inject("inject_dns_error")
    time.sleep(1)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]

    print("\n[*] 表现特征观测: IP Ping 与 DNS 解析测试 ...")
    ping_ip = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    dns_test = inj_pool.host_inj.api._run_cmd(target_host, "ping -c 4 -W 2 www.baidu.com")
    
    print(f"[IP Ping 输出]:\n{ping_ip.strip()}\n")
    print(f"[DNS 解析输出]:\n{dns_test.strip()}")
    
    domain_fail = any(err in dns_test.lower() for err in ["temporary failure", "name resolution", "not known", "bad address", "100% packet loss"])
    
    if ("0% packet loss" in ping_ip) and domain_fail:
        print("✅ 表现特征符合: IP 畅通，但应用层域名解析瘫痪")
    else:
        print("❌ 表现特征不符")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} resolv.conf ...")
    dns_res = inj_pool.host_inj.api._run_cmd(target_host, "cat /etc/resolv.conf")
    print(f"[Agent 诊断输出 (resolv.conf)]:\n{dns_res.strip()}")
    
    if "nameserver 0.1.2.3" in dns_res:
        print("✅ Agent 识别成功: nameserver 已被成功篡改为 0.1.2.3")
    else:
        print("❌ Agent 识别失败")


def test_cpu_overload(inj_pool: FaultInjector, cfg: dict):
    print("\n>>> (6) 测试: CPU 资源过载 (CPU Overload)")
    inj_pool.inject("inject_high_cpu_load")
    time.sleep(2)

    target_host = cfg["target"]
    h2_ip = cfg["peer_ip_same_subnet"]

    print("\n[*] 表现特征观测: Ping 延迟观测 ...")
    # 预热 ARP
    inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=1) 
    
    ping_res = inj_pool.host_inj.api.linux_ping(target_host, h2_ip, count=4)
    print(f"[Ping 输出 (剔除了首包初始化干扰，此时的波动均为真实抖动)]:\n{ping_res.strip()}")
    print("✅ 表现特征符合: 验证完成 (请观察上方输出的 mdev 是否升高)")

    print(f"\n[*] Agent 识别逻辑观测: 检查主机 {target_host} 进程状态 ...")
    ps_res = inj_pool.host_inj.api._run_cmd(target_host, "sh -c 'ps aux | grep [d]d'")
    print(f"[Agent 诊断输出 (ps)]:\n{ps_res.strip()}")
    
    if "dd" in ps_res and "/dev/zero" in ps_res:
        print("✅ Agent 识别成功: 发现存在异常的 CPU 满载进程 (dd if=/dev/zero...)")
    else:
        print("❌ Agent 识别失败")


if __name__ == "__main__":
    # 为了复用底层的部署/销毁逻辑，我们需要导入 HOST 的配置字典
    from fault_inject_pool import HOST_INJECT_INPUT
    
    lab = "static_routing"
    
    # 执行测试
    run_scenario_tests(lab, [
        # test_interface_down, 
        # test_ip_misconfig, 
        test_default_route_missing, 
        # test_arp_poisoning, 
        test_dns_error, 
        # test_cpu_overload
    ], HOST_INJECT_INPUT)