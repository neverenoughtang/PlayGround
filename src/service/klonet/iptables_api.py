from .base_api import KlonetBaseAPI
from typing import Optional, List

class KlonetIptablesAPI(KlonetBaseAPI):
    """
    Klonet 实验环境 Linux 网络控制接口 (基于 iptables + iproute2)。
    
    优势：
    1. 兼容性极佳：适用于几乎所有 Linux 镜像，无需额外安装 nftables。
    2. 功能完备：覆盖路由查看、链路控制、流量阻断。
    """

    # --- IPTables 核心管理 (防火墙层) ---

    def iptables_list_rules(self, host_name: str, table: str = "filter") -> str:
        """
        列出指定表的所有规则。
        使用 -n (numeric) 避免 DNS 解析，使用 -v (verbose) 查看计数器，-L (list)。
        """
        command = f"iptables -t {table} -L -n -v --line-numbers"
        return self._run_cmd(host_name, command)

    def iptables_flush(self, host_name: str, table: str = "filter") -> str:
        """
        清空指定表的规则 (Flush) 并删除自定义链。
        """
        # -F: Flush chains, -X: Delete user-defined chains
        command = f"iptables -t {table} -F && iptables -t {table} -X"
        return self._run_cmd(host_name, command)

    def iptables_add_drop_rule(
        self, 
        host_name: str, 
        chain: str = "INPUT", 
        protocol: str = None, 
        dport: int = None, 
        extra_args: str = ""
    ) -> str:
        """
        [核心故障注入] 添加一条丢弃(DROP)规则。
        
        默认使用 -I (Insert) 将规则插入到链首，确保优先级最高。
        
        Args:
            host_name: 主机名
            chain: 链名称 (INPUT: 进本机的流量, FORWARD: 转发的流量)
            protocol: 协议 (tcp, udp, icmp, 或数字如 89)
            dport: 目标端口 (仅 tcp/udp 有效)
            extra_args: 其他参数 (如 "-s 192.168.1.0/24")
        """
        cmd_parts = [f"iptables -I {chain} 1"] # 插入到第1行
        
        if protocol:
            cmd_parts.append(f"-p {protocol}")
        
        if dport and protocol in ["tcp", "udp"]:
            cmd_parts.append(f"--dport {dport}")
            
        if extra_args:
            cmd_parts.append(extra_args)
            
        cmd_parts.append("-j DROP") # 动作：直接丢弃
        
        full_command = " ".join(cmd_parts)
        return self._run_cmd(host_name, full_command)

    def iptables_custom_cmd(self, host_name: str, args: str) -> str:
        """
        执行任意 iptables 命令。
        例如: args="-A INPUT -p icmp -j REJECT"
        """
        return self._run_cmd(host_name, f"iptables {args}")

    # --- Linux 原生路由与接口工具 (iproute2) ---
    # 这些命令与 iptables 配合使用，效果拔群

    def linux_show_route(self, host_name: str) -> str:
        """查看内核路由表 (FIB)。"""
        return self._run_cmd(host_name, "ip route show")

    def linux_add_route(self, host_name: str, target: str, next_hop: str) -> str:
        """手动添加静态路由 (模拟路由劫持/修复)。"""
        return self._run_cmd(host_name, f"ip route add {target} via {next_hop}")

    def linux_del_route(self, host_name: str, target: str) -> str:
        """删除路由条目 (模拟路由黑洞)。"""
        return self._run_cmd(host_name, f"ip route del {target}")

    def linux_set_link_status(self, host_name: str, interface: str, status: str) -> str:
        """修改接口状态 (up/down) (模拟物理断网)。"""
        # 兼容性处理：有的系统用 ifconfig，但 ip link 是现代标准
        return self._run_cmd(host_name, f"ip link set dev {interface} {status}")

    def linux_ping(self, host_name: str, target_ip: str, count: int = 3) -> str:
        """连通性测试。"""
        # -c 次数, -W 超时(秒)
        return self._run_cmd(host_name, f"ping -c {count} -W 1 {target_ip}")


if __name__ == "__main__":
    print("======= Iptables 故障注入测试 =======")
    
    # 在此处切换你的场景名称进行测试
    # 可选: "simple_bgp_test", "ospf_enterprise_test", "rip_internet_test", "static_routing_test"
    CURRENT_SCENARIO = "static_routing_test"
    
    # 简单的后缀处理，防止逻辑对应不上
    SCENARIO_KEY = CURRENT_SCENARIO.replace("_test", "")
    
    print(f"当前测试场景: 【 {CURRENT_SCENARIO} 】")

    try:
        ipt_api = KlonetIptablesAPI(CURRENT_SCENARIO)
        
        # 1. 寻找测试目标
        hosts = ipt_api.get_all_hosts()
        if not hosts:
            hosts = ipt_api.get_all_routers()
            
        if not hosts:
            print("❌ 错误: 拓扑中未找到任何主机或路由器。")
            exit(1)
            
        target_node = hosts[0]
        print(f"选定测试目标 (Victim): {target_node}")

        # --- 环境初始化 ---
        print("\n--- [Init] 清空旧规则 ---")
        ipt_api.iptables_flush(target_node)
        print("Iptables 规则已清空。")

        # --- 场景测试 ---

        if "bgp" in SCENARIO_KEY:
            print("\n>>> BGP 场景故障注入 (TCP 179)")
            print("正在注入: Drop TCP port 179...")
            ipt_api.iptables_add_drop_rule(target_node, chain="INPUT", protocol="tcp", dport=179)
            
            # 验证
            rules = ipt_api.iptables_list_rules(target_node)
            print(rules)
            # [修正] 分开匹配 DROP 和 端口，因为它们在输出中相隔很远
            if "DROP" in rules and ("dpt:179" in rules or "dpt:bgp" in rules):
                print("✅ 故障注入成功: BGP 端口已被封锁。")
            else:
                print("❌ 规则未在列表中发现。")

        elif "ospf" in SCENARIO_KEY:
            print("\n>>> OSPF 场景故障注入 (Protocol 89)")
            print("正在注入: Drop Protocol 89 (OSPF)...")
            ipt_api.iptables_add_drop_rule(target_node, chain="INPUT", protocol="89")
            
            # 验证
            rules = ipt_api.iptables_list_rules(target_node)
            print(rules)
            if "89" in rules and "DROP" in rules:
                print("✅ 故障注入成功: OSPF 报文将被丢弃。")
            else:
                print("❌ 规则验证失败。")

        elif "rip" in SCENARIO_KEY:
            print("\n>>> RIP 场景故障注入 (UDP 520)")
            print("正在注入: Drop UDP port 520...")
            ipt_api.iptables_add_drop_rule(target_node, chain="INPUT", protocol="udp", dport=520)
            
            rules = ipt_api.iptables_list_rules(target_node)
            print(rules)
            # [修正] 分开匹配 DROP 和 端口
            if "DROP" in rules and ("dpt:520" in rules or "dpt:route" in rules):
                print("✅ 故障注入成功: RIP 更新将被拦截。")
            else:
                print("❌ 规则验证失败。")

        elif "static" in SCENARIO_KEY:
            print("\n>>> 静态路由与连通性测试")
            
            # 1. 接口层故障
            target_iface = "eth0"
            print(f"正在关闭接口 {target_iface}...")
            ipt_api.linux_set_link_status(target_node, target_iface, "down")
            
            link_info = ipt_api._run_cmd(target_node, f"ip link show {target_iface}")
            if "DOWN" in link_info:
                print(f"✅ 物理层故障生效: {target_iface} is DOWN.")
            
            ipt_api.linux_set_link_status(target_node, target_iface, "up")
            print(f"接口已恢复 UP。")
            
            # 2. 防火墙层故障 (ICMP)
            print("\n正在注入: Drop ICMP (Ping)...")
            ipt_api.iptables_add_drop_rule(target_node, chain="INPUT", protocol="icmp")
            
            ping_res = ipt_api.linux_ping(target_node, "127.0.0.1", count=2)
            print(ping_res)
            if "100% packet loss" in ping_res:
                print("✅ 防火墙生效: 无法 Ping 通。")
            else:
                print("⚠️  Warning: Ping 依然通畅。这在测试 127.0.0.1 时是正常的，因为 Loopback 流量通常被默认放行。")

        else:
            print(f"场景名称 {CURRENT_SCENARIO} 未匹配到特定测试逻辑，仅执行了清理。")

    except Exception as e:
        print(f"❌ 发生异常: {e}")





