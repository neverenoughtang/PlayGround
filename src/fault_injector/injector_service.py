import socket
import time
from service.klonet import KlonetFRRAPI, KlonetSDNAPI, KlonetBMv2API, KlonetOVSAPI
import logging
system_logger = logging.getLogger("PlayGround")

class ServiceFaultInjector:
    """
    网络中间件与路由协议层故障注入器 (纯净版)
    涵盖 6 大类：FRR 基础与静态黑洞、BGP、OSPF、RIP、SDN/OVS、P4/BMv2
    注：本类仅包含注入方法，供基准测试平台验证和 Agent 诊断使用。
    """
    def __init__(self, lab_name: str):
        self.lab_name = lab_name
        self.logger = system_logger
        self.frr = KlonetFRRAPI(lab_name)
        self.sdn = KlonetSDNAPI(lab_name)
        self.bmv2 = KlonetBMv2API(lab_name)
        self.ovs = KlonetOVSAPI(lab_name)

    # ================= 1. FRR / 防火墙 =================
    def inject_route_missing(self, router_name: str, network: str):
        """
        [注入] 1. 目标网段路由缺失
        输入: router_name, network (如 192.168.4.0/24)
        说明: 直接从路由器的内核 FIB 表中删除去往特定网段的路由。
              导致路由器收到前往该网段的包时无路可走，直接丢弃并返回不可达。
        """
        self.logger.info(f"正在注入故障: {router_name} 删除目标网段路由 {network}")
        # 使用 ip route del 直接删除该网段的路由条目
        self.frr._run_cmd(router_name, f"ip route del {network}")

    def inject_static_route_blackhole(self, router_name: str, network: str):
        """
        [注入] 2. 静态黑洞路由
        输入: router_name, network (如 192.168.4.0/24)
        说明: 下发黑洞路由，精确丢弃发往某业务网段的所有数据包。        
        """
        self.logger.info(f"正在注入故障: {router_name} 黑洞路由 {network}")
        # [修复] 放弃 vtysh，直接使用 ip route replace 修改内核 FIB 表，优先级最高，绝对拦截！
        self.frr._run_cmd(router_name, f"ip route replace blackhole {network}")

    def inject_router_data_plane_drop(self, router_name: str):
        """
        [注入] 3. 路由器数据面 ICMP 防火墙阻断
        输入: router_name
        说明: 在 Linux 路由器的数据面(利用FRR API底层的系统执行能力)强行丢弃转发包，模拟 ACL 拦截。
        """
        self.logger.info(f"正在注入故障: {router_name} 全局 ICMP 阻断")
        self.frr._run_cmd(router_name, "iptables -I FORWARD -p icmp -j DROP")


    # ================= 2. BGP =================
    def inject_bgp_neighbor_shutdown(self, router_name: str, asn: int, neighbor_ip: str):
        """
        [注入] 4. 管理性关闭 BGP 邻居
        输入: router_name, asn, neighbor_ip
        说明: 通过 FRR 接口下发 shutdown 指令，强行断开 BGP TCP 会话，导致跨域路由被撤销。
        """
        self.logger.info(f"正在注入故障: {router_name} 关闭 BGP 邻居 {neighbor_ip}")
        self.frr._run_cmd(router_name, f"vtysh -c 'conf t' -c 'router bgp {asn}' -c 'neighbor {neighbor_ip} shutdown'")

    def inject_bgp_withdraw_route(self, router_name: str, asn: int, network: str):
        """
        [注入] 5. BGP 撤销网段宣告 (及重分发)
        输入: router_name, asn, network
        说明: 移除目标网段的 network 宣告，并关闭直连路由重分发，彻底将该网段从 BGP 路由表中抹除，引发回程路由黑洞。
        """
        self.logger.info(f"正在注入故障: {router_name} 撤销 BGP 路由 {network} 并关闭重分发")
        # [修复] 同时执行 no network 和 no redistribute connected，确保路由彻底从 BGP 消失
        self.frr._run_cmd(router_name, f"vtysh -c 'conf t' -c 'router bgp {asn}' -c 'no network {network}' -c 'no redistribute connected'")

    def inject_bgp_wrong_peer_asn(self, router_name: str, asn: int, neighbor_ip: str, wrong_peer_asn: int):
        """
        [注入] 6. BGP 邻居 AS 号配置错误
        输入: router_name, asn, neighbor_ip, wrong_peer_asn
        说明: 篡改 remote-as 参数，导致 BGP 在交换 OPEN 报文时发生 AS 匹配错误，状态机卡死在 Active 状态。
        """
        self.logger.info(f"正在注入故障: {router_name} 错误 AS {wrong_peer_asn}")
        self.frr._run_cmd(router_name, f"vtysh -c 'conf t' -c 'router bgp {asn}' -c 'neighbor {neighbor_ip} remote-as {wrong_peer_asn}'")


    # ================= 3. OSPF =================
    def inject_ospf_passive_interface(self, router_name: str, interface: str):
        """
        [注入] 7. OSPF 接口静默
        输入: router_name, interface
        说明: 将指定接口配置为被动接口（Passive Interface），停止在该接口上发送 OSPF Hello 报文。
        这将导致该链路的 OSPF 邻居关系因超时而断开，并引发网络路由的动态重收敛。
        """
        self.logger.info(f"正在注入故障: {router_name} 接口 {interface} 设为 Passive")
        self.frr._run_cmd(router_name, f"vtysh -c 'conf t' -c 'router ospf' -c 'passive-interface {interface}'")

    def inject_ospf_cost_spike(self, router_name: str, interface: str):
        """
        [注入] 8. OSPF 接口开销突增
        输入: router_name, interface
        说明: 篡改指定 OSPF 接口的链路度量值（Cost）至极限大值（如 65000）。
        该操作会立即触发 LSA 泛洪与全网 SPF 算法重新计算，诱导网络流量避开此链路，产生次优路径绕路。
        """
        self.logger.info(f"正在注入故障: {router_name} 接口 {interface} Cost 突增")
        self.frr._run_cmd(router_name, f"vtysh -c 'conf t' -c 'interface {interface}' -c 'ip ospf cost 65000'")

    def inject_ospf_daemon_crash(self, router_name: str):
        """
        [注入] 9. OSPF 进程崩溃
        输入: router_name
        说明: 在底层 Linux 系统中强制杀死 ospfd 核心守护进程。这会导致该路由器负责的所有 OSPF 
        路由瞬间从内核 FIB 表中撤销，模拟控制面进程意外崩溃的严重故障。
        """
        self.logger.info(f"正在注入故障: {router_name} OSPF 进程崩溃")
        self.frr._run_cmd(router_name, "pkill ospfd")


    # ================= 4. RIP =================
    def inject_rip_passive_interface(self, router_name: str, interface: str):
        """
        [注入] 11. RIP 接口静默
        输入: router_name, interface
        说明: 在 RIP 进程中将指定接口设为 passive-interface，使其只接收不发送 RIP 组播路由更新，导致对端邻居的路由在老化后断开。
        """
        self.logger.info(f"注入: {router_name} 接口 {interface} 停止发送 RIP")
        # 直接通过 CLI 将接口设为 passive
        cmd = f"vtysh -c 'conf t' -c 'router rip' -c 'passive-interface {interface}'"
        self.frr._run_cmd(router_name, cmd)
        time.sleep(170)

    def inject_rip_route_filter(self, router_name: str):
        """
        [注入] 11. RIP 路由过滤 (新)
        输入: router_name
        说明: 利用 distribute-list 强行屏蔽所有 RIP 出方向路由
        """
        self.logger.info(f"注入: {router_name} 配置 distribute-list 拦截路由")
        cmd = "vtysh -c 'conf t' -c 'access-list 99 deny any' -c 'router rip' -c 'distribute-list 99 out'"
        self.frr._run_cmd(router_name, cmd)
        time.sleep(170)

    def inject_rip_metric_offset(self, router_name: str):
        """
        [注入] 12. RIP 度量值篡改 (新)
        输入: router_name
        说明: 利用 offset-list 强行把所有出方向的 RIP 路由跳数(Metric)增加 15，直接导致路由不可达(16跳不可达)
        """
        self.logger.info(f"注入: {router_name} 配置 offset-list 篡改度量值")
        cmd = "vtysh -c 'conf t' -c 'access-list 98 permit any' -c 'router rip' -c 'offset-list 98 out 15'"
        self.frr._run_cmd(router_name, cmd)
        time.sleep(170)


    # ================= 5. SDN / OVS =================
    def inject_sdn_controller_crash(self, controller_name: str):
        """
        [注入] 13. Ryu 控制器崩溃
        输入: controller_name
        说明: 利用系统级强制查杀指令 (killall / pkill) 销毁 Ryu 控制器的核心 Python 进程。切断 OpenFlow 协议的南向控制链，
        导致全网数据面失去动态路由计算能力，新数据流 (如 ARP) 因无法 Packet-In 而被丢弃。
        """
        self.logger.info(f"正在注入故障: 控制器 {controller_name} 崩溃")
        # [核心修复]: 使用 sh -c 包裹，确保 || 逻辑符号生效，使用 killall 强杀
        self.sdn._run_cmd(controller_name, "sh -c 'killall -9 ryu-manager || killall -9 python || pkill -9 python'")

    def inject_ovs_disconnect_controller(self, switch_name: str):
        """
        [注入] 14. OVS 断开控制器连接
        输入: switch_name
        说明: 动态遍历 OVS 上所有的虚拟网桥，并通过 ovs-vsctl 命令行删除其指向 Ryu 控制器的配置。
        在 fail_mode=secure 的安全设定下，强行割裂数据面与控制面的联系，使得交换机退化为静默丢包状态。
        """
        self.logger.info(f"正在注入故障: OVS {switch_name} 断开控制器")
        # [核心修复]: 使用 sh -c 包裹，确保 $() 和 for 循环能够被 Bash 解析
        self.ovs._run_cmd(switch_name, "sh -c 'for br in $(ovs-vsctl list-br); do ovs-vsctl del-controller $br; done'")

    def inject_ovs_global_drop_flow(self, switch_name: str):
        """
        [注入] 15. OVS 注入高优先级全局 DROP 流表
        输入: switch_name
        说明: 动态遍历网桥，并利用 ovs-ofctl 命令行向 OVS 强行下发一条 priority=65535 (OpenFlow 最高优先级) 且 
        action 为 drop 的恶意流表规则。该规则将在数据面的最前端截获并销毁所有报文，制造全局流量黑洞。
        """
        self.logger.info(f"正在注入故障: OVS {switch_name} DROP 流表")
        # [核心修复]: 使用 sh -c 包裹，确保网桥动态获取成功
        self.ovs._run_cmd(switch_name, "sh -c 'for br in $(ovs-vsctl list-br); do ovs-ofctl add-flow $br priority=65535,actions=drop; done'")


    # ================= 6. BMv2 / P4 =================
    def inject_bmv2_process_crash(self, switch_name: str):
        """
        [注入] 16. BMv2 P4 引擎崩溃
        输入: switch_name
        说明: 直接杀死底层宿主机中运行的 P4 软件交换机进程 (simple_switch)，
        导致数据平面彻底瘫痪，所有流经该节点的流量静默丢失。
        """
        self.logger.info(f"正在注入故障: P4 交换机 {switch_name} 进程崩溃")
        self.bmv2._run_cmd(switch_name, "pkill simple_switch")

    def _get_p4_handle(self, switch_name: str, table_name: str, ip_with_prefix: str):
        """内部工具方法：根据 IP 提取十进制格式的 P4 流表 Handle"""
        ip_str = ip_with_prefix.split('/')[0]
        ip_hex = socket.inet_aton(ip_str).hex()
        
        dump_res = self.bmv2._run_cmd(switch_name, f"sh -c 'echo \"table_dump {table_name}\" | simple_switch_CLI'")
        lines = dump_res.split('\n')
        for i, line in enumerate(lines):
            if ip_hex in line:
                for j in range(i, -1, -1):
                    if "Dumping entry" in lines[j]:
                        handle_hex = lines[j].split()[-1] # 例如获取到 "0x1"
                        # [修复2] 将 16 进制强转为 10 进制字符串，确保 CLI 100% 识别
                        return str(int(handle_hex, 16)) 
        return None

    def inject_p4_table_drop(self, switch_name: str, table_name: str, match_key: str):
        """
        [注入] 17. P4 表项级 DROP 动作注入
        输入: switch_name, table_name, match_key
        说明: 采用先删除后添加的策略，通过 simple_switch_CLI 从指定的匹配动作表中删去合法的转发条目，
        并植入一条针对目标 IP (match_key) 的 MyIngress.drop 丢弃表项，实现数据面的精准拦截。
        """
        # 记得加上 --thrift-port 9090
        self.logger.info(f"正在注入故障: P4 {switch_name} 篡改 {match_key} 为 Drop 动作 (Delete & Add)")
        # 直接使用官方 API 获取 handle (它自带了精准解析和端口参数)
        handle = self.bmv2.get_handle_by_ip(switch_name, table_name, match_key)
        
        if handle is not None:
            # 放弃低效的 Delete & Add，直接利用 API 进行动作修改
            self.bmv2.bmv2_table_modify(switch_name, table_name, "MyIngress.drop", handle, [])
        else:
            self.logger.warning(f"未找到 {match_key} 的现有表项，跳过修改。")

    def inject_p4_wrong_forwarding(self, switch_name: str, table_name: str, match_key: str, wrong_port: str):
        """
        [注入] 18. P4 表项级转发端口篡改
        输入: switch_name, table_name, match_key, wrong_port
        说明: 采用先删除后添加的策略，通过 simple_switch_CLI 篡改针对特定目标 IP 的转发表项参数。
        保留合法的转发动作，但将包的 Egress 端口强行修改为无效或错误的端口 (wrong_port)，
        引发黑洞路由。
        """
        # 记得加上 --thrift-port 9090
        self.logger.info(f"正在注入故障: P4 {switch_name} 篡改 {match_key} 出端口至 {wrong_port} (Delete & Add)")
        handle = self.bmv2.get_handle_by_ip(switch_name, table_name, match_key)
        
        if handle is not None:
            # 篡改动作参数：传入假的 MAC(全0) 和 错的端口(wrong_port)
            self.bmv2.bmv2_table_modify(switch_name, table_name, "MyIngress.ipv4_forward", handle, ["00:00:00:00:00:00", str(wrong_port)])
        else:
            self.logger.warning(f"未找到 {match_key} 的现有表项，跳过修改。")
