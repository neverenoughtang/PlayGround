# src/agent/test/inject_test_cases.py

"""
复合故障注入终极测试用例库 (共 30 例)
- 完美覆盖全部 7 大网络场景
- 完美覆盖全部 58 种细分故障
- 包含 10 条单故障、10 条双故障交叉、10 条三故障交叉
"""

COMPOSITE_TEST_CASES = [
    # ==========================================
    # 级别 1: 单一故障注入测试 (10 条)
    # ==========================================
    # {
    #     "level": "Single",
    #     "lab_name": "static_routing",
    #     "fault_query": "在路由器 r1 上删除发往业务网段的路由。",
    #     "expected_faults_contained": ["route_missing"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "simple_bgp",
    #     "fault_query": "给路由器 r2 发往邻居的路由加上极高的 MED 值。",
    #     "expected_faults_contained": ["bgp_med_spike"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "ospf_enterprise",
    #     "fault_query": "把核心路由器 c1 的互联接口设置为 OSPF 被动接口(passive interface)。",
    #     "expected_faults_contained": ["ospf_passive_interface"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "rip_internet",
    #     "fault_query": "配置 RIP passive-interface 让路由器 r1 的接口变静默。",
    #     "expected_faults_contained": ["rip_passive_interface"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "p4_star",
    #     "fault_query": "直接杀掉 bmv2 交换机 s1 的 simple_switch 进程。",
    #     "expected_faults_contained": ["p4_bmv2_process_crash"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "sdn_openflow",
    #     "fault_query": "杀掉 Ryu 控制器 c0 的进程。",
    #     "expected_faults_contained": ["sdn_controller_crash"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "ai_inference",
    #     "fault_query": "直接终止 server 算力节点上的 python3 推理进程。",
    #     "expected_faults_contained": ["ai_service_crash"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "static_routing",
    #     "fault_query": "在核心路由器 r2 上注入一条黑洞路由(blackhole)。",
    #     "expected_faults_contained": ["static_route_blackhole"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "simple_bgp",
    #     "fault_query": "将路由器 r1 的 BGP 邻居 administratively shutdown。",
    #     "expected_faults_contained": ["bgp_neighbor_shutdown"]
    # },
    # {
    #     "level": "Single",
    #     "lab_name": "sdn_openflow",
    #     "fault_query": "在 OVS 交换机 s1 上使用 del-controller 断开其与控制器的连接。",
    #     "expected_faults_contained": ["ovs_disconnect"]
    # },

    # ==========================================
    # 级别 2: 双重复合故障交叉测试 (10 条)
    # ==========================================
    {
        "level": "Double",
        "lab_name": "static_routing",
        "fault_query": "在路由器 r1 的 FORWARD 链上丢弃所有 ICMP 数据包，并且给主机 h1 注入 50% 的链路丢包。",
        "expected_faults_contained": ["data_plane_drop", "link_loss"]
    },
    # {
    #     "level": "Double",
    #     "lab_name": "simple_bgp",
    #     "fault_query": "撤销路由器 r2 上的业务网段 BGP 宣告，同时给主机 h2 的网卡加上 300ms 的链路延迟。",
    #     "expected_faults_contained": ["bgp_withdraw_route", "link_latency"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "ospf_enterprise",
    #     "fault_query": "将汇聚路由器 d1 的某条核心链路 OSPF 开销(cost)改为 65000，并且让主机 h1 的链路产生严重网络抖动。",
    #     "expected_faults_contained": ["ospf_cost_spike", "link_jitter"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "rip_internet",
    #     "fault_query": "用 distribute-list 过滤掉路由器 r2 发出的 RIP 路由，并把主机 pc1 的网卡限速到 100kbps 造成拥塞。",
    #     "expected_faults_contained": ["rip_route_filter", "link_bandwidth"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "p4_star",
    #     "fault_query": "把 P4 交换机 s1 上某条路由表项的动作改成 drop，然后把主机 h2 的 IP 错误地配置为 11.22.33.44/24。",
    #     "expected_faults_contained": ["p4_table_drop", "ip_misconfig"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "sdn_openflow",
    #     "fault_query": "在交换机 s2 下发一条优先级为 65535 的全局丢弃(drop)流表，并且删掉主机 h3 的默认路由。",
    #     "expected_faults_contained": ["ovs_global_drop", "default_route_missing"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "ai_inference",
    #     "fault_query": "用 stress-ng 把 server 算力节点的 CPU 彻底打满，然后伪造客户端 client1 的 ARP MAC 地址为 ab:bc:cd:de:ef:fa。",
    #     "expected_faults_contained": ["compute_cpu_starvation", "arp_poisoning"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "static_routing",
    #     "fault_query": "直接杀掉路由器 r2 上的 zebra 守护进程，并且强制关闭主机 h3 的全部网络接口。",
    #     "expected_faults_contained": ["frr_service_down", "interface_down"]
    # },
    # {
    #     "level": "Double",
    #     "lab_name": "simple_bgp",
    #     "fault_query": "把路由器 r3 的 BGP 邻居对端 AS 号配错，接着把主机 h1 的 DNS 指向一个错误的无效地址。",
    #     "expected_faults_contained": ["bgp_wrong_peer_asn", "dns_error"]
    # },
    {
        "level": "Double",
        "lab_name": "ospf_enterprise",
        "fault_query": "强制杀掉接入路由器 d1 的 ospfd 进程，另外用 stress-ng 脚本把主机 h2 的 CPU 载满导致系统卡顿。",
        "expected_faults_contained": ["ospf_daemon_crash", "cpu_overload"]
    },

    # ==========================================
    # 级别 3: 三重复合故障交叉测试 (10 条)
    # ==========================================
    # {
    #     "level": "Triple",
    #     "lab_name": "static_routing",
    #     "fault_query": "关闭路由器 r1 的内核 IPv4 转发功能；把路由器 r2 连着主机的那个接口 IP 篡改掉；最后在主机 h1 上注入一条发往错误网关的静态路由。",
    #     "expected_faults_contained": ["ip_forward_disabled", "router_interface_ip_wrong", "routing_error"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "simple_bgp",
    #     "fault_query": "用防火墙阻断路由器 r1 的 BGP TCP 179 端口；通过 route-map 异常调高路由器 r2 的 Local Preference 属性；并且将主机 h2 的子网掩码错误地改为 /31。",
    #     "expected_faults_contained": ["acl_blocking_bgp_traffic", "bgp_local_pref_spike", "mask_error"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "ospf_enterprise",
    #     "fault_query": "使用 iptables 拦截路由器 c2 的 OSPF (协议号89) 报文；把路由器 d2 的 OSPF Area 错误宣告到 Area 99；最后修改内核参数把主机 h4 的可用临时端口耗尽。",
    #     "expected_faults_contained": ["acl_blocking_ospf_traffic", "ospf_area_misconfig", "host_port_exhaustion"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "rip_internet",
    #     "fault_query": "用 offset-list 把路由器 r3 上的 RIP 路由跳数增加 15；在路由器 r4 的入方向 DROP 掉 UDP 520 端口的更新流量；并强制把路由器 r1 的 RIP 运行版本改成 version 1 制造错配。",
    #     "expected_faults_contained": ["rip_metric_offset", "acl_blocking_rip_traffic", "rip_version_mismatch"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "p4_star",
    #     "fault_query": "把 P4 交换机 s1 的某条转发端口篡改为不存在的端口 99；删除 s1 上匹配某台主机的转发表项；并且将 s1 的默认转发动作设置为 drop。",
    #     "expected_faults_contained": ["p4_wrong_forwarding", "p4_table_entry_missing", "p4_default_action_drop"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "sdn_openflow",
    #     "fault_query": "把 OVS 交换机 s2 连向控制器的地址改成一个错误的 IP；强制把交换机 s3 的南向协议降级成 OpenFlow10；并在交换机 s1 注入一条高优先级 normal 动作流表覆盖精细策略。",
    #     "expected_faults_contained": ["southbound_wrong_controller", "southbound_protocol_mismatch", "flow_rule_shadowing"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "ai_inference",
    #     "fault_query": "消耗掉 server 算力服务器 95% 的内存使其溢出；在 server 服务端用防火墙拦截 TCP 8000 端口阻断业务；并在中间交换机 tor1 针对业务目的端口做静默丢弃(DROP)导致跨层黑洞。",
    #     "expected_faults_contained": ["compute_memory_exhaustion", "inference_port_blocked", "cross_layer_traffic_blackhole"]
    # },
    {
        "level": "Triple",
        "lab_name": "ospf_enterprise",
        "fault_query": "把路由器 d2 的两端 Hello 定时器改成不一致；在路由器 c1 开启 OSPF MD5 认证并配个错误的密码；最后给主机 h3 注入 50% 的链路层丢包。",
        "expected_faults_contained": ["ospf_neighbor_misconfig", "ospf_auth_misconfig", "link_loss"]
    },
    # {
    #     "level": "Triple",
    #     "lab_name": "rip_internet",
    #     "fault_query": "把路由器 r2 的 RIP 基础计时器全部改成 999 秒导致收敛极慢；在路由器 r3 的路由进程里撤销宣告某个直连网段；并且占用主机 pc2 的 CPU 制造过载卡顿。",
    #     "expected_faults_contained": ["rip_timer_misconfig", "rip_network_withdraw", "cpu_overload"]
    # },
    # {
    #     "level": "Triple",
    #     "lab_name": "sdn_openflow",
    #     "fault_query": "下发一条让流量从原端口直接打回的自环流表到交换机 s2；把 OVS 交换机 s3 的 fail-mode 强行设置为 secure；最后人为把主机 h1 的网卡接口 down 掉。",
    #     "expected_faults_contained": ["flow_rule_loop", "ovs_fail_secure", "interface_down"]
    # }
]