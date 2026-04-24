# src/agent/diagnose_agent/inject_test_cases.py

COMPOSITE_TEST_CASES = [
    # ==========================================
    # 级别 1: 单一故障注入测试 (包含多节点同故障) (10 条)
    # ==========================================
    {
        "level": "Single", "lab_name": "static_routing",
        "fault_query": "在路由器 r1, r2, r3 上同时删除发往业务网段的路由。",
        "expected_faults_contained": ["route_missing"]
    },
    {
        "level": "Single", "lab_name": "simple_bgp",
        "fault_query": "给路由器 r2 发往邻居的路由加上极高的 MED 值。",
        "expected_faults_contained": ["bgp_med_spike"]
    },
    {
        "level": "Single", "lab_name": "ospf_enterprise",
        "fault_query": "把核心路由器 c1 和 c2 的互联接口均设置为 OSPF 被动接口(passive interface)。",
        "expected_faults_contained": ["ospf_passive_interface"]
    },
    {
        "level": "Single", "lab_name": "rip_internet",
        "fault_query": "配置 RIP passive-interface 让路由器 r4 的接口变静默。",
        "expected_faults_contained": ["rip_passive_interface"]
    },
    {
        "level": "Single", "lab_name": "p4_star",
        "fault_query": "把主机 h1, h2, h3 的 IP 全部错误配置为 11.22.33.44/24。",
        "expected_faults_contained": ["ip_misconfig"]
    },
    {
        "level": "Single", "lab_name": "sdn_openflow",
        "fault_query": "杀掉 Ryu 控制器 c0 的进程。",
        "expected_faults_contained": ["sdn_controller_crash"]
    },
    {
        "level": "Single", "lab_name": "ai_inference",
        "fault_query": "直接终止 server 算力节点上的 python3 推理进程。",
        "expected_faults_contained": ["ai_service_crash"]
    },
    {
        "level": "Single", "lab_name": "static_routing",
        "fault_query": "在核心路由器 r2 上注入一条黑洞路由(blackhole)。",
        "expected_faults_contained": ["static_route_blackhole"]
    },
    {
        "level": "Single", "lab_name": "simple_bgp",
        "fault_query": "将路由器 r1 和 r3 的 BGP 邻居 administratively shutdown。",
        "expected_faults_contained": ["bgp_neighbor_shutdown"]
    },
    {
        "level": "Single", "lab_name": "sdn_openflow",
        "fault_query": "在 OVS 交换机 s1 和 s2 上使用 del-controller 断开其与控制器的连接。",
        "expected_faults_contained": ["ovs_disconnect"]
    },

    # ==========================================
    # 级别 2: 双重复合故障 (空间隔离防掩盖) (10 条)
    # ==========================================
    {
        "level": "Double", "lab_name": "static_routing",
        "fault_query": "在路由器 r1 的 FORWARD 链上丢弃 ICMP 数据包，另外在完全不同的网络区域给主机 h6 注入 50% 的链路丢包。",
        "expected_faults_contained": ["data_plane_drop", "link_loss"]
    },
    {
        "level": "Double", "lab_name": "simple_bgp",
        "fault_query": "撤销路由器 r2 上的业务网段 BGP 宣告，同时给另一侧的主机 h12 的网卡加上 300ms 的链路延迟。",
        "expected_faults_contained": ["bgp_withdraw_route", "link_latency"]
    },
    {
        "level": "Double", "lab_name": "ospf_enterprise",
        "fault_query": "将汇聚路由器 d1 的某条核心链路 OSPF 开销改为 65000，并且让边缘的主机 h8 产生严重网络抖动。",
        "expected_faults_contained": ["ospf_cost_spike", "link_jitter"]
    },
    {
        "level": "Double", "lab_name": "rip_internet",
        "fault_query": "用 distribute-list 过滤掉路由器 r2 发出的 RIP 路由，并将路由器 r4 下挂的主机 pc10 的网卡限速到 100kbps 造成拥塞。",
        "expected_faults_contained": ["rip_route_filter", "link_bandwidth"]
    },
    {
        "level": "Double", "lab_name": "p4_star",
        "fault_query": "把 P4 交换机 s1 上发往 h1 的表项动作改成 drop，然后把主机 h12 的默认路由直接删掉。",
        "expected_faults_contained": ["p4_table_drop", "default_route_missing"]
    },
    {
        "level": "Double", "lab_name": "sdn_openflow",
        "fault_query": "在交换机 s2 下发全局丢弃(drop)流表，并且把 s5 交换机下挂的 h11 的 DNS 指向一个错误的无效地址。",
        "expected_faults_contained": ["ovs_global_drop", "dns_error"]
    },
    {
        "level": "Double", "lab_name": "ai_inference",
        "fault_query": "用 stress-ng 把 server 算力节点的 CPU 彻底打满，并在远端的 client9 上伪造 ARP MAC 地址。",
        "expected_faults_contained": ["compute_cpu_starvation", "arp_poisoning"]
    },
    {
        "level": "Double", "lab_name": "static_routing",
        "fault_query": "直接杀掉路由器 r3 上的 zebra 守护进程，并且强制关闭主机 h1 的全部网络接口。",
        "expected_faults_contained": ["frr_service_down", "interface_down"]
    },
    {
        "level": "Double", "lab_name": "simple_bgp",
        "fault_query": "把路由器 r4 的 BGP 邻居对端 AS 号配错，并且将主机 h2 的子网掩码错误地改为 /30。",
        "expected_faults_contained": ["bgp_wrong_peer_asn", "mask_error"]
    },
    {
        "level": "Double", "lab_name": "ospf_enterprise",
        "fault_query": "强制杀掉接入路由器 a1 的 ospfd 进程，另外用 stress-ng 把最远端主机 h7 的 CPU 载满导致系统卡顿。",
        "expected_faults_contained": ["ospf_daemon_crash", "cpu_overload"]
    },

    # ==========================================
    # 级别 3: 三重复合故障 (分布在不同网段防掩盖) (10 条)
    # ==========================================
    {
        "level": "Triple", "lab_name": "static_routing",
        "fault_query": "关闭路由器 r1 的内核 IPv4 转发功能；把路由器 r3 连着主机的那个接口 IP 篡改掉；最后在独立的主机 h9 上注入一条发往错误网关的静态路由。",
        "expected_faults_contained": ["ip_forward_disabled", "router_interface_ip_wrong", "routing_error"]
    },
    {
        "level": "Triple", "lab_name": "simple_bgp",
        "fault_query": "阻断路由器 r1 的 BGP TCP 179 端口；异常调高路由器 r3 的 Local Preference 属性；并且耗尽主机 h14 的可用临时端口。",
        "expected_faults_contained": ["acl_blocking_bgp_traffic", "bgp_local_pref_spike", "host_port_exhaustion"]
    },
    {
        "level": "Triple", "lab_name": "ospf_enterprise",
        "fault_query": "拦截路由器 c1 的 OSPF 报文；把汇聚路由器 d2 的 OSPF Area 错误宣告到 Area 99；最后拔掉边缘主机 h2 的网线(interface down)。",
        "expected_faults_contained": ["acl_blocking_ospf_traffic", "ospf_area_misconfig", "interface_down"]
    },
    {
        "level": "Triple", "lab_name": "rip_internet",
        "fault_query": "用 offset-list 把路由器 r1 上的 RIP 路由跳数增加 15；在路由器 r4 的入方向 DROP 掉 UDP 520 端口更新；把主机 pc8 的 CPU 性能压榨到极限。",
        "expected_faults_contained": ["rip_metric_offset", "acl_blocking_rip_traffic", "cpu_overload"]
    },
    {
        "level": "Triple", "lab_name": "p4_star",
        "fault_query": "把 P4 交换机 s1 发往 h3 的转发端口篡改；删除 s1 上匹配 h7 的转发表项；给 h10 注入 50% 丢包率。",
        "expected_faults_contained": ["p4_wrong_forwarding", "p4_table_entry_missing", "link_loss"]
    },
    {
        "level": "Triple", "lab_name": "sdn_openflow",
        "fault_query": "把 OVS 交换机 s1 连向控制器的地址改错；强制把交换机 s4 的南向协议降级成 OpenFlow10；在主机 h5 注入高延迟。",
        "expected_faults_contained": ["southbound_wrong_controller", "southbound_protocol_mismatch", "link_latency"]
    },
    {
        "level": "Triple", "lab_name": "ai_inference",
        "fault_query": "消耗掉 server 算力服务器 95% 的内存；在 spine1 上注入 TCP RST 报文阻断会话；把 client3 的接口配置错误的子网掩码。",
        "expected_faults_contained": ["compute_memory_exhaustion", "tcp_rst_injection", "mask_error"]
    },
    {
        "level": "Triple", "lab_name": "ospf_enterprise",
        "fault_query": "把路由器 d1 的 Hello 定时器改错；在核心路由器 c3 开启不一致的 OSPF MD5 认证；最后给主机 h6 设置极低的令牌桶限速带宽。",
        "expected_faults_contained": ["ospf_neighbor_misconfig", "ospf_auth_misconfig", "link_bandwidth"]
    },
    {
        "level": "Triple", "lab_name": "rip_internet",
        "fault_query": "把路由器 r2 的 RIP 计时器改大导致收敛极慢；在路由器 r4 里撤销宣告某个直连网段；并且在主机 pc5 注入静态 ARP 毒化目标。",
        "expected_faults_contained": ["rip_timer_misconfig", "rip_network_withdraw", "arp_poisoning"]
    },
    {
        "level": "Triple", "lab_name": "sdn_openflow",
        "fault_query": "下发一条让流量从原端口直接打回的自环流表到交换机 s2；把 OVS 交换机 s3 的 fail-mode 设置为 secure；最后删除主机 h12 的默认网关。",
        "expected_faults_contained": ["flow_rule_loop", "ovs_fail_secure", "default_route_missing"]
    }
]