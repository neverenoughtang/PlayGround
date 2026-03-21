from .base_api import KlonetBaseAPI
from typing import List, Optional, Dict
import re

class KlonetOVSAPI(KlonetBaseAPI):
    """
    在 Klonet 实验环境中与 Open vSwitch (OVS) 交互的接口类。
    
    主要工具:
    1. ovs-vsctl: 管理 OVS 数据库 (网桥、端口、控制器连接)。
    2. ovs-ofctl: 管理 OpenFlow 流表 (查看、添加、删除流表项)。
    
    适用场景:
    - 传统二层交换 (NORMAL 模式) 的状态检查。
    - 手动下发 OpenFlow 规则进行流量干预。
    - 端口统计与排错。
    """

    # --- 1. OVS 配置管理 (ovs-vsctl) ---

    def ovs_show_summary(self, switch_name: str) -> str:
        """
        显示 OVS 的整体配置摘要。
        包含网桥(Bridge)、端口(Port)、接口(Interface)的层级关系，以及控制器连接状态。
        
        Args:
            switch_name: 交换机节点名称 (如 "s1")
        
        Returns:
            output: 'ovs-vsctl show' 的输出文本
        """
        command = "ovs-vsctl show"
        return self._run_cmd(switch_name, command)

    def ovs_list_bridges(self, switch_name: str) -> List[str]:
        """
        获取交换机上所有的网桥名称列表。
        
        Args:
            switch_name: 交换机节点名称
            
        Returns:
            bridges: 网桥名称列表 (如 ['br0', 'br1'])
        """
        command = "ovs-vsctl list-br"
        output = self._run_cmd(switch_name, command)
        # 过滤空行并转为列表
        return [line.strip() for line in output.split('\n') if line.strip()]

    def ovs_set_fail_mode(self, switch_name: str, bridge: str, mode: str) -> str:
        """
        设置网桥的故障模式 (Fail Mode)。
        
        Args:
            switch_name: 交换机名称
            bridge: 网桥名称 (通常是 "br0")
            mode: 
                - 'standalone': 连不上控制器时充当普通交换机 (默认/推荐)。
                - 'secure': 连不上控制器时中断转发，等待控制器指令。
        """
        if mode not in ['standalone', 'secure']:
            raise ValueError("Mode must be 'standalone' or 'secure'")
        command = f"ovs-vsctl set-fail-mode {bridge} {mode}"
        return self._run_cmd(switch_name, command)

    # --- 2. OpenFlow 流表管理 (ovs-ofctl) ---

    def ovs_dump_flows(self, switch_name: str, bridge: str = "br0", protocol: str = "OpenFlow13") -> str:
        """
        查看交换机当前的流表 (Flow Table)。
        这是排查丢包、环路最核心的命令。
        
        Args:
            switch_name: 交换机名称
            bridge: 网桥名称
            protocol: OpenFlow 协议版本 (默认 OpenFlow13)
            
        Returns:
            flows: 流表详细信息 (Cookie, Priority, Match, Actions)
        """
        # -O 指定协议版本，防止版本不匹配导致无法显示
        command = f"ovs-ofctl -O {protocol} dump-flows {bridge}"
        return self._run_cmd(switch_name, command)

    def ovs_add_flow(self, switch_name: str, bridge: str, flow_str: str, protocol: str = "OpenFlow13") -> str:
        """
        手动添加一条 OpenFlow 流表项。
        
        Args:
            switch_name: 交换机名称
            bridge: 网桥名称
            flow_str: 流表定义字符串 (例如 "priority=100,ip,actions=drop")
            
        Returns:
            output: 命令执行结果
        """
        command = f"ovs-ofctl -O {protocol} add-flow {bridge} '{flow_str}'"
        return self._run_cmd(switch_name, command)

    def ovs_del_flows(self, switch_name: str, bridge: str, filter_str: str = "", protocol: str = "OpenFlow13") -> str:
        """
        删除匹配的流表项。
        
        Args:
            switch_name: 交换机名称
            bridge: 网桥名称
            filter_str: 筛选条件 (例如 "ip" 或 "in_port=1")。留空则清空所有流表。
        """
        if filter_str:
            command = f"ovs-ofctl -O {protocol} del-flows {bridge} '{filter_str}'"
        else:
            command = f"ovs-ofctl -O {protocol} del-flows {bridge}"
        return self._run_cmd(switch_name, command)

    # --- 3. 统计与监控 ---

    def ovs_dump_ports(self, switch_name: str, bridge: str = "br0", protocol: str = "OpenFlow13") -> str:
        """
        查看端口统计信息 (收发包数量、字节数、丢包数)。
        
        Args:
            switch_name: 交换机名称
            bridge: 网桥名称
            
        Returns:
            stats: 端口统计文本
        """
        command = f"ovs-ofctl -O {protocol} dump-ports {bridge}"
        return self._run_cmd(switch_name, command)


if __name__ == "__main__":
    print("======= OVS API 场景测试 =======")
    
    # 使用你指定的静态路由场景进行测试
    # 注意：static_routing 场景中可能包含作为二层转发的 OVS 交换机
    SCENARIO_NAME = "static_routing_test"
    
    print(f"当前测试场景: 【 {SCENARIO_NAME} 】")
    
    try:
        ovs_api = KlonetOVSAPI(SCENARIO_NAME)
        
        # 1. 自动探测交换机
        # 优先从 switches 列表中找，如果没有，尝试从 nodes 中根据镜像名判断
        switches = ovs_api.get_all_ovs()
        
        if not switches:
            print("⚠️ 警告: 当前拓扑中未检测到明确定义的 switch 节点。")
            print("尝试检查是否有运行 OVS 的混合节点...")
            # 备选逻辑：有些拓扑可能把 OVS 当 router 用，或者没标记清楚
            # 这里简单处理：如果没有交换机，我们无法进行 OVS 测试
            print("❌ 无法继续：没有可用的 OVS 交换机。")
            exit(1)
            
        target_sw = switches[0]
        bridge_name = "br0" # Klonet 默认网桥名
        print(f"选定测试交换机: {target_sw}")

        # --- 测试 1: 配置检查 ---
        print("\n--- 1. OVS 配置摘要 (ovs-vsctl) ---")
        summary = ovs_api.ovs_show_summary(target_sw)
        print(summary)
        
        # 验证网桥是否存在
        bridges = ovs_api.ovs_list_bridges(target_sw)
        print(f"检测到网桥: {bridges}")
        if bridge_name not in bridges:
            print(f"⚠️ 默认网桥 {bridge_name} 不存在，切换到 {bridges[0] if bridges else 'None'}")
            bridge_name = bridges[0] if bridges else "br0"

        # --- 测试 2: 流表检查 ---
        print(f"\n--- 2. 当前流表 (ovs-ofctl) [Bridge: {bridge_name}] ---")
        flows = ovs_api.ovs_dump_flows(target_sw, bridge_name)
        print(flows)
        
        # 判断是否为 NORMAL 模式 (非 SDN 场景通常是 NORMAL)
        if "actions=NORMAL" in flows:
            print("✅ 检测到 NORMAL 转发规则，交换机处于传统二层模式。")
        else:
            print("ℹ️ 未检测到 NORMAL 规则 (可能是纯 OpenFlow 模式或空表)。")

        # --- 测试 3: 手动流表干预 ---
        print("\n--- 3. 注入测试流表 (Drop ICMP) ---")
        # 规则: 优先级 100, 协议 icmp, 动作丢弃
        test_flow = "priority=100,icmp,actions=drop"
        print(f"正在添加: {test_flow}")
        ovs_api.ovs_add_flow(target_sw, bridge_name, test_flow)
        
        # 验证
        flows_after = ovs_api.ovs_dump_flows(target_sw, bridge_name)
        if "actions=drop" in flows_after and "icmp" in flows_after:
            print("✅ 流表添加成功！ICMP 流量将被该交换机拦截。")
        else:
            print("❌ 流表添加失败。")

        # --- 测试 4: 端口统计 ---
        print("\n--- 4. 端口统计信息 ---")
        ports_stat = ovs_api.ovs_dump_ports(target_sw, bridge_name)
        # 简单打印前几行
        print("\n".join(ports_stat.split('\n')[:5]) + "\n...")

        # --- 测试 5: 清理 ---
        print("\n--- 5. 清理测试流表 ---")
        # 仅删除刚才添加的 icmp 规则，避免误删 NORMAL 规则导致断网
        ovs_api.ovs_del_flows(target_sw, bridge_name, filter_str="icmp")
        print("清理完成。")
        
        # 再次确认
        flows_final = ovs_api.ovs_dump_flows(target_sw, bridge_name)
        if "actions=drop" not in flows_final:
            print("✅ 状态已恢复。")

    except Exception as e:
        print(f"❌ 测试异常: {e}")