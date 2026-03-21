import sys
import os
import re
import time
from typing import List, Optional, Union


# --- [修复] 兼容 MCP 调用和直接运行 ---
try:
    # 尝试作为包内模块导入 (供 MCP 使用)
    from .base_api import KlonetBaseAPI
except ImportError:
    # 如果失败，说明是直接运行此脚本 (供调试使用)
    from base_api import KlonetBaseAPI

class KlonetFRRAPI(KlonetBaseAPI):
    """
    在 Klonet 实验环境中与 FRR (Free Range Routing) 路由守护进程交互的接口类。
    
    功能覆盖：
    1. 基础配置查看与命令执行
    2. 路由表检查
    3. OSPF/BGP/RIP 协议状态与路由查询
    4. 静态路由管理
    5. 基础网络连通性测试 (Ping)
    """

    # --- 基础通用命令 ---

    def frr_show_route(self, device_name: str) -> str:
        """
        显示 FRR 实例的路由表 (show ip route)。
        """
        command = "vtysh -c 'show ip route'"
        return self._run_cmd(device_name, command)

    def frr_exec(self, device_name: str, command: str) -> str:
        """
        在 FRR 实例上执行任意 vtysh 命令。
        """
        safe_command = command.replace("'", "'\\''")
        full_command = f"vtysh -c '{safe_command}'"
        return self._run_cmd(device_name, full_command)

    def frr_show_running_config(self, device_name: str) -> str:
        """
        显示 FRR 实例的当前运行配置。
        """
        command = "vtysh -c 'show running-config'"
        return self._run_cmd(device_name, command)

    def frr_save_config(self, device_name: str) -> str:
        """
        保存当前配置到启动配置文件 (write memory)。
        """
        command = "vtysh -c 'write memory'"
        return self._run_cmd(device_name, command)

    def frr_ping(self, device_name: str, target_ip: str, count: int = 3) -> str:
        """
        从指定设备发起 Ping 测试。
        虽然这是系统级命令，但作为网络验证必不可少。
        
        Args:
            device_name: 源设备名称
            target_ip: 目标 IP 地址
            count: 发包数量，默认为 3
        """
        # 注意：这里直接调用系统 ping，而不是进入 vtysh，通常在仿真容器内这样更直接
        command = f"ping -c {count} {target_ip}"
        return self._run_cmd(device_name, command)

    # --- OSPF 相关命令 ---

    def frr_get_ospf_conf(self, device_name: str) -> str:
        """获取 FRR 实例的 OSPF 协议配置部分。"""
        command = "vtysh -c 'show ip ospf'"
        return self._run_cmd(device_name, command)

    def frr_get_ospf_neighbors(self, device_name: str) -> str:
        """获取 FRR 实例的 OSPF 邻居列表 (Full/2-Way 状态至关重要)。"""
        command = "vtysh -c 'show ip ospf neighbor'"
        return self._run_cmd(device_name, command)

    def frr_get_ospf_routes(self, device_name: str) -> str:
        """获取 FRR 实例的 OSPF 路由条目。"""
        command = "vtysh -c 'show ip route ospf'"
        return self._run_cmd(device_name, command)

    def frr_get_ospf_interfaces(self, device_name: str) -> str:
        """获取 FRR 实例的 OSPF 接口详情。"""
        command = "vtysh -c 'show ip ospf interface'"
        return self._run_cmd(device_name, command)

    # --- RIP 相关命令 (新增) ---

    def frr_get_rip_status(self, device_name: str) -> str:
        """
        获取 RIP 协议的全局状态。
        包含定时器信息、运行状态等。
        """
        command = "vtysh -c 'show ip rip status'"
        return self._run_cmd(device_name, command)

    def frr_get_rip_routes(self, device_name: str) -> str:
        """
        获取通过 RIP 协议学习到的路由 (标记为 R)。
        """
        command = "vtysh -c 'show ip route rip'"
        return self._run_cmd(device_name, command)

    # --- BGP 相关命令 ---

    def frr_get_bgp_conf(self, device_name: str) -> str:
        """获取 FRR 实例的 BGP 路由表 (RIB)。"""
        command = "vtysh -c 'show ip bgp'"
        return self._run_cmd(device_name, command)
    
    def frr_get_bgp_summary(self, device_name: str) -> str:
        """
        获取 BGP 邻居摘要信息。
        这是排查 BGP 最常用的命令，显示邻居状态 (State/PfxRcd)。
        """
        command = "vtysh -c 'show ip bgp summary'"

        return self._run_cmd(device_name, command)

    def frr_conf(self, device_name: str, conf_commands: List[str]) -> str:
        """
        批量配置 FRR 实例 (进入 conf t 模式)。
        """
        command = 'vtysh -c "conf t"'
        for cmd in conf_commands:
            safe_cmd = cmd.replace('"', '\\"')
            command += f' -c "{safe_cmd}"'
        command += ' -c "end" -c "write"'
        return self._run_cmd(device_name, command)

    def frr_add_static_route(self, device_name: str, route: str, next_hop: str) -> str:
        """向 FRR 实例添加静态路由。"""
        cmds = [f"ip route {route} {next_hop}"]
        return self.frr_conf(device_name, cmds)

    def frr_del_static_route(self, device_name: str, route: str, next_hop: str) -> str:
        """从 FRR 实例删除静态路由。"""
        cmds = [f"no ip route {route} {next_hop}"]
        return self.frr_conf(device_name, cmds)

    def frr_add_bgp_network(self, device_name: str, network: str, asn: int) -> str:
        """向 FRR 实例添加 BGP 网络通告。"""
        cmds = [
            f"router bgp {asn}",
            f"network {network}"
        ]
        return self.frr_conf(device_name, cmds)

    def frr_del_bgp_network(self, device_name: str, network: str, asn: int) -> str:
        """从 FRR 实例删除 BGP 网络通告。"""
        cmds = [
            f"router bgp {asn}",
            f"no network {network}"
        ]
        return self.frr_conf(device_name, cmds)

    def frr_get_bgp_asn_number(self, device_name: str) -> int:
        """
        获取 FRR 实例的本地 BGP AS 号。
        Returns: AS 编号 (int), 若未找到返回 -1
        """
        command = "vtysh -c 'show bgp summary'"
        result = self._run_cmd(device_name, command)
        
        match = re.search(r"local AS number\s+(\d+)", result)
        if match:
            return int(match.group(1))
        
        match_alt = re.search(r"AS number\s+(\d+)", result)
        if match_alt:
            return int(match_alt.group(1))

        print(f"[WARN] Could not find AS number in BGP summary for {device_name}")
        return -1


if __name__ == "__main__":
    print("======= FRR API 多场景测试环节 =======")
    
    #在此处切换你的场景名称进行测试
    # 可选: "simple_bgp", "ospf_enterprise", "rip_internet", "static_routing"
    CURRENT_SCENARIO = "rip_internet" 
    
    print(f"当前测试场景: 【 {CURRENT_SCENARIO} 】")

    try:
        # 1. 初始化 API
        # 注意：实际运行时 lab_name 必须与 Klonet 中部署的一致
        frr_api = KlonetFRRAPI(CURRENT_SCENARIO)

        # 2. 获取拓扑中的第一个路由器作为主要测试对象
        routers = frr_api.get_all_routers()

        if not routers:
            print("❌ 未在拓扑中发现路由器，请检查 lab_name 是否正确或拓扑是否已启动。")
            exit(1)

        target_router = routers[0]
        print(f"选定测试设备: {target_router}")
        
        # --- 通用基础检查 ---
        print("\n--- [Base] 运行配置检查 ---")
        print(frr_api.frr_show_running_config(target_router)[:200] + "...") # 防刷屏
        
        # --- 场景特定测试 ---
        
        if CURRENT_SCENARIO == "simple_bgp":
            print("\n>>> 进入 BGP 专项测试")
            # 1. 检查 ASN
            asn = frr_api.frr_get_bgp_asn_number(target_router)
            print(f"Local AS Number: {asn}")
            
            # 2. 检查 BGP 邻居状态 (关键)
            print("正在检查 BGP 邻居概要 (寻找 State/PfxRcd)...")
            bgp_sum = frr_api.frr_get_bgp_summary(target_router)
            print(bgp_sum)
            if "Established" in bgp_sum or re.search(r"\s+\d+\s+0\s+0\s+\d+", bgp_sum):
                print("✅ 检测到 BGP 邻居已建立或正在交换前缀。")
            else:
                print("⚠️ BGP 邻居似乎未建立 (Idle/Active)，请检查网络连通性。")
                
            # 3. 尝试宣告一个测试网段
            print("测试添加 BGP Network 宣告...")
            if asn != -1:
                frr_api.frr_add_bgp_network(target_router, "99.99.99.0/24", asn)
                print("指令已下发，请检查 show run 确认。")

        elif CURRENT_SCENARIO == "ospf_enterprise":
            print("\n>>> 进入 OSPF 专项测试")
            # 1. 检查 OSPF 邻居
            print("正在检查 OSPF 邻居 (寻找 Full 状态)...")
            neighbors = frr_api.frr_get_ospf_neighbors(target_router)
            print(neighbors)
            if "Full" in neighbors:
                print("✅ OSPF 邻居关系正常 (Full)。")
            else:
                print("⚠️ 未检测到 Full 状态邻居，请检查链路状态。")
            
            # 2. 检查 OSPF 路由表
            print("正在读取 OSPF 路由表...")
            routes = frr_api.frr_get_ospf_routes(target_router)
            print(routes)

        elif CURRENT_SCENARIO == "rip_internet":
            print("\n>>> 进入 RIP 专项测试")
            # 1. 检查 RIP 进程状态
            print("检查 RIP 全局状态...")
            status = frr_api.frr_get_rip_status(target_router)
            print(status)
            
            # 2. 检查 RIP 路由
            print("检查 RIP 学习到的路由 (Codes: R)...")
            rip_routes = frr_api.frr_get_rip_routes(target_router)
            print(rip_routes)
            if "R " in rip_routes or "R>" in rip_routes:
                print("✅ 成功学习到 RIP 路由。")
            else:
                print("⚠️ 路由表中未发现 RIP 路由，请检查版本兼容性(v1/v2)或网络通断。")

        elif CURRENT_SCENARIO == "static_routing_test":
            print("\n>>> 进入 静态路由 专项测试")
            # 1. 添加静态路由
            test_net = "192.168.99.0/24"
            next_hop = "127.0.0.1" # 仅演示用，实际应改为拓扑中存在的直连IP
            print(f"测试添加静态路由: {test_net} via {next_hop}")
            frr_api.frr_add_static_route(target_router, test_net, next_hop)
            
            # 2. 验证
            routes = frr_api.frr_show_route(target_router)
            if test_net.split('/')[0] in routes:
                print("✅ 静态路由添加成功。")
            else:
                print("❌ 静态路由未在路由表中显示。")
                
            # 3. Ping 测试 (模拟连通性验证)
            # 注意：需替换为实际存在的IP才能 ping 通
            print(f"尝试 Ping 测试 (NextHop: {next_hop})...") 
            ping_res = frr_api.frr_ping(target_router, next_hop, count=2)
            print(ping_res)

        else:
            print(f"未知场景: {CURRENT_SCENARIO}")

    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")