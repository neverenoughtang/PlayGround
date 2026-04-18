FAULT_REGISTRY = {
    "common_link": """链路层故障（适用于所有网络场景）: 
    - link_loss: 发生在 ubuntu 主机上，通过 Linux TC netem 注入丢包规则，表现为网络链路具有一定丢包率（如50%），导致通信不稳定、延迟高或部分数据包丢失
    - link_latency: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟规则，表现为网络延迟异常偏高但抖动极小，导致业务响应缓慢
    - link_jitter: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟抖动规则，表现为网络延迟忽高忽低极不稳定，mdev 数值显著偏高
    - link_bandwidth: 发生在 ubuntu 主机上，通过 Linux TC tbf 令牌桶限速，表现为传输速度被严重限流，网络拥塞严重""",

    "common_host": """主机层故障（适用于所有网络场景）: 
    - ip_misconfig: 发生在 ubuntu 主机上，通过 flush 网卡 IP 后配置错误地址，表现为主机无法与同网段或其他节点正常通信，IP 丢失或配错
    - default_route_missing: 发生在 ubuntu 主机上，通过删除默认路由，表现为主机同网段通信正常但跨网段通信完全不可达
    - arp_poisoning: 发生在 ubuntu 主机上，通过静态绑定伪造 MAC 地址，表现为主机局域网内无法与特定目标通信，ARP 缓存表出现异常条目
    - interface_down: 发生在 ubuntu 主机上，通过 ip link set down 关闭网卡，表现为主机似乎彻底脱网，所有网络连接中断
    - dns_error: 发生在 ubuntu 主机上，通过修改 /etc/resolv.conf 指向错误 DNS 服务器，表现为主机无法访问外部域名网站，域名解析失败
    - cpu_overload: 发生在 ubuntu 主机上，通过 stress-ng 打满 CPU 资源，表现为主机系统严重卡顿，业务处理缓慢，CPU 空闲率趋近于0
    - routing_error: 发生在 ubuntu 主机上，通过添加错误的静态路由指向非预期网关，表现为主机无法访问特定外部网段，数据包走向异常
    - mask_error: 发生在 ubuntu 主机上，通过配置错误的子网掩码（如/30），表现为同网段内的部分相邻主机无法直接通信
    - host_port_exhaustion: 发生在 ubuntu 主机上，通过 sysctl 限制可用源端口范围为极窄值，表现为主机应用程序抛出"无法分配请求的地址"错误，无法发起新连接""",

    "static_routing": """FRR 路由器故障（当前场景特有）: 
    - route_missing: 发生在 frr 路由器上，通过 ip route del 删除目标网段路由，表现为主机发往特定网段的跨网段流量完全不通，提示网络不可达
    - static_route_blackhole: 发生在 frr 路由器上，通过 ip route replace blackhole 将目标网段路由改为黑洞，表现为某业务网段的数据包被神秘丢弃，流量有去无回
    - data_plane_drop: 发生在 frr 路由器上，通过 iptables FORWARD 链阻断 ICMP 报文，表现为 Ping 测试全部超时但其他 TCP/UDP 连接可能正常
    - frr_service_down: 发生在 frr 路由器上，通过 pkill zebra/bgpd 杀掉 FRR 守护进程，表现为路由器突然停止一切动态路由转发能力，导致局部网络瘫痪
    - ip_forward_disabled: 发生在 frr 路由器上，通过 sysctl 关闭 IPv4 转发开关，表现为路由器本机可达但转发经过它的业务流量全部中断
    - router_interface_ip_wrong: 发生在 frr 路由器上，通过 flush 接口 IP 后配置错误地址，表现为与该路由器直连的网段全部异常，ARP 与网关解析出现问题""",

    "simple_bgp": """BGP 路由器故障（当前场景特有）: 
    - bgp_neighbor_shutdown: 发生在 frr 路由器上，通过 vtysh 配置 neighbor shutdown 管理性关闭 BGP 邻居，表现为某节点跨域通信突然中断，邻居连接失败
    - bgp_withdraw_route: 发生在 frr 路由器上，通过 vtysh 删除 network 宣告或 redistribute connected，表现为邻居正常但某远端网段突然不可达
    - bgp_wrong_peer_asn: 发生在 frr 路由器上，通过 vtysh 配置错误的对端 AS 号，表现为某处 BGP 邻居始终无法建立，状态长期停留在 Idle 或 Active
    - acl_blocking_bgp_traffic: 发生在 frr 路由器上，通过 iptables 阻断 TCP 179 端口，表现为 BGP 会话断开后无法重连
    - bgp_local_pref_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 local-preference 值（如999），表现为跨域流量突然绕行到非预期路径
    - bgp_med_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 MED 值（如9999），表现为对端更偏好其他入口，业务路径切换异常""",

    "ospf_enterprise": """OSPF 路由器故障（当前场景特有）: 
    - ospf_passive_interface: 发生在 frr 路由器上，通过 vtysh 配置 passive-interface 使接口停止发送 Hello 报文，表现为某处原本正常的 OSPF 邻居突然断开
    - ospf_cost_spike: 发生在 frr 路由器上，通过 vtysh 设置接口 OSPF cost 为异常高值（如65000），表现为流量发生大规模路径切换
    - ospf_daemon_crash: 发生在 frr 路由器上，通过 pkill ospfd 杀掉 OSPF 守护进程，表现为某路由器完全丢失所有 OSPF 路由
    - acl_blocking_ospf_traffic: 发生在 frr 路由器上，通过 iptables 阻断 IP 协议号89（OSPF），表现为链路物理畅通但 OSPF 邻居持续超时消失
    - ospf_neighbor_misconfig: 发生在 frr 路由器上，通过 vtysh 设置不一致的 Hello 定时器，表现为 OSPF 邻接关系始终无法建立
    - ospf_area_misconfig: 发生在 frr 路由器上，通过 vtysh 将接口网段宣告到错误区域，表现为某些区域间路由传播异常，部分 OSPF 邻居无法正常建立
    - ospf_auth_misconfig: 发生在 frr 路由器上，通过 vtysh 单侧配置 OSPF 认证或配置不一致密钥，表现为链路本身可达但某条 OSPF 邻接关系突然无法维持""",

    "rip_internet": """RIP 路由器故障（当前场景特有）: 
    - rip_passive_interface: 发生在 frr 路由器上，通过 vtysh 配置 passive-interface 使接口停止发送 RIP 更新，表现为邻居无法再收到本端发送的 RIP 更新
    - rip_route_filter: 发生在 frr 路由器上，通过 vtysh 配置 distribute-list 阻断路由发布，表现为特定网段的对端学不到该路由
    - rip_metric_offset: 发生在 frr 路由器上，通过 vtysh offset-list 增加 RIP 度量值至15或更高，表现为特定 RIP 路由完全无法跨越多跳传播（度量值达16视为不可达）
    - acl_blocking_rip_traffic: 发生在 frr 路由器上，通过 iptables 阻断 UDP 520 端口，表现为邻居长时间学不到任何新路由宣告
    - rip_version_mismatch: 发生在 frr 路由器上，通过 vtysh 强制修改 RIP 版本（v1/v2 不兼容），表现为部分网段路由神秘丢失或聚合错误，BadPackets 计数增加
    - rip_timer_misconfig: 发生在 frr 路由器上，通过 vtysh timers basic 设置异常大的定时器值（如999秒），表现为路由收敛需要数十分钟甚至无法收敛
    - rip_network_withdraw: 发生在 frr 路由器上，通过 vtysh 删除 network 宣告，表现为原本可达的远端网段突然消失""",

    "p4_star": """P4 交换机故障（当前场景特有）: 
    - p4_bmv2_process_crash: 发生在 bmv2 交换机上，通过 pkill simple_switch 杀掉 BMv2 运行时进程，表现为途经 P4 交换机的数据流彻底中断
    - p4_table_drop: 发生在 bmv2 交换机上，通过修改 P4 转发表项动作为 drop，表现为某主机通往某 IP 丢包严重
    - p4_wrong_forwarding: 发生在 bmv2 交换机上，通过修改 P4 转发表项参数为错误 MAC 或端口号，表现为发往某个特定 IP 的数据包始终无法到达
    - p4_table_entry_missing: 发生在 bmv2 交换机上，通过删除 P4 转发表项，表现为原本互通的两台主机忽然彻底无法通信
    - p4_default_action_drop: 发生在 bmv2 交换机上，通过修改 P4 表默认动作为 drop，表现为新出现或未显式配置的流量全部无法通过交换机""",

    "sdn_openflow": """SDN 交换机/控制器故障（当前场景特有）: 
    - sdn_controller_crash: 发生在 ryu 控制器上，通过 pkill ryu-manager/python 杀掉控制器进程，表现为 SDN 网络失去控制，新上的主机无法通信
    - ovs_disconnect: 发生在 ovs 交换机上，通过 ovs-vsctl del-controller 删除控制器配置，表现为某台交换机不再接受控制器管理
    - ovs_global_drop: 发生在 ovs 交换机上，通过 ovs-ofctl 注入高优先级全局 DROP 流表，表现为途经某台交换机的所有流量都被无差别丢弃
    - southbound_wrong_controller: 发生在 ovs 交换机上，通过 ovs-vsctl set-controller 配置错误的控制器地址，表现为交换机仍在运行但始终无法与控制器建立控制连接
    - southbound_protocol_mismatch: 发生在 ovs 交换机上，通过 ovs-vsctl 设置不兼容的 OpenFlow 协议版本，表现为控制器提示报文格式无法识别，下属 OVS 失去动态控制能力
    - flow_rule_shadowing: 发生在 ovs 交换机上，通过 ovs-ofctl 注入高优先级通配规则覆盖控制器策略，表现为业务流量不再按控制器预期路径转发，网络策略似乎整体失效
    - flow_rule_loop: 发生在 ovs 交换机上，通过 ovs-ofctl 注入自回环流表规则（in_port=X, output:X），表现为网络出现流量死循环，带宽被迅速挤占
    - ovs_fail_secure: 发生在 ovs 交换机上，通过 ovs-vsctl set-fail-mode secure 关闭本地兜底转发，表现为控制器短暂异常后交换机不再进行本地兜底转发""",

    "ai_inference": """AI 推理服务故障（当前场景特有）:
    - ai_service_crash: 发生在 ubuntu 主机上，通过 pkill python3 杀掉 AI 推理服务进程，表现为 AI 助手突然不再回复任何消息
    - compute_cpu_starvation: 发生在 ubuntu 主机上，通过 stress-ng 打满 CPU 资源，表现为 AI 吐字极度缓慢
    - compute_memory_exhaustion: 发生在 ubuntu 主机上，通过 stress-ng 占用大量内存（如95%），表现为 AI 服务突然无响应，推理服务频繁超时
    - inference_port_blocked: 发生在 ubuntu 主机或 frr 路由器上，通过 iptables 阻断推理服务端口（如8000），表现为能 Ping 通服务器但推理 API 全部超时
    - tcp_rst_injection: 发生在 frr 路由器上，通过 iptables FORWARD 链注入 TCP RST 报文，表现为连接建立后很快被异常重置
    - cross_layer_traffic_blackhole: 发生在 frr 路由器上，通过 iptables FORWARD 链选择性丢弃特定目的端口流量，表现为跨机房请求算力节点时业务大包被神秘丢弃"""
}