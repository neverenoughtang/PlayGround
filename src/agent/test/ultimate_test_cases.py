# ultimate_test_cases.py

TEST_CASES = [
    # ======== 1. 链路层故障 (4种, 混合场景) ======== #
    {
        "fault_name": "link_latency",
        "deploy_query": "我要一个静态路由网络",
        "fault_query": "在 h2 注入 500 ms 链路高延迟"
    },
    {
        "fault_name": "link_loss",
        "deploy_query": "我要一个 BGP 网络",
        "fault_query": "在 h1 注入 60% 链路丢包"
    },
    {
        "fault_name": "link_jitter",
        "deploy_query": "我要一个 AI 推理场景网络",
        "fault_query": "在 h1 注入 500 ms 链路抖动"
    },   
    {
        "fault_name": "link_bandwidth",
        "deploy_query": "我要一个 P4 路由网络",
        "fault_query": "在 h2 注入链路带宽限制"
    },

    # ======== 2. 主机层故障 (9种, 混合场景) ======== #
    {
        "fault_name": "ip_misconfig",
        "deploy_query": "我要一个没有任何路由协议的网络",
        "fault_query": "把 h1 的 IP 配置为 11.22.33.44/24"
    },
    {
        "fault_name": "default_route_missing",
        "deploy_query": "我要一个外部网关协议的网络",
        "fault_query": "随便挑一台主机，删掉默认路由"
    },
    {
        "fault_name": "arp_poisoning",
        "deploy_query": "我要一个大型的企业级dhcp网络",
        "fault_query": "随便挑一台主机，伪造它的 MAC 地址为 ab:bc:cd:de:ef:fa"
    },  
    {
        "fault_name": "interface_down",
        "deploy_query": "我要一个rip中小型网络",
        "fault_query": "挑一台重要的主机，关闭它的全部接口"
    },
    {
        "fault_name": "dns_error",
        "deploy_query": "我要一个使用 bmv2 交换机的星状网络",
        "fault_query": "把 h3 的 DNS 配错"
    },
    {
        "fault_name": "cpu_overload",
        "deploy_query": "我要一个数据面和控制面分离的网络，最好包含 ovs",
        "fault_query": "把 h2 的 CPU 载满"
    },
    {
        "fault_name": "mask_error",
        "deploy_query": "我要一个包含 http 服务场景的网络",
        "fault_query": "将客户端的子网掩码改为 /31"
    },    
    {
        "fault_name": "routing_error",
        "deploy_query": "我要一个简单的静态网络",
        "fault_query": "在 h1 注入错误的静态路由"
    },
    {
        "fault_name": "host_port_exhaustion",
        "deploy_query": "我要一个包含 ryu 控制器的网络",
        "fault_query": "把 h3 的端口耗尽"
    },

    # ======== 3. FRR 路由器故障 (6种, static_routing) ======== #
    {
        "fault_name": "route_missing",
        "deploy_query": "部署一个经典的静态路由拓扑",
        "fault_query": "在路由器上删除发往某业务网段的路由"
    },
    {
        "fault_name": "static_route_blackhole",
        "deploy_query": "创建一个三层静态路由环境",
        "fault_query": "在核心路由器上注入一条黑洞路由"
    },
    {
        "fault_name": "data_plane_drop",
        "deploy_query": "启动 static_routing 实验",
        "fault_query": "在路由器 FORWARD 链上丢弃所有 ICMP 数据包"
    },
    {
        "fault_name": "frr_service_down",
        "deploy_query": "准备静态路由网络",
        "fault_query": "直接杀掉路由器上的 zebra 守护进程"
    },
    {
        "fault_name": "ip_forward_disabled",
        "deploy_query": "部署 static_routing 场景",
        "fault_query": "关闭路由器的内核 IPv4 转发功能"
    },
    {
        "fault_name": "router_interface_ip_wrong",
        "deploy_query": "我要静态路由拓扑",
        "fault_query": "把路由器连着主机的那个接口 IP 篡改掉"
    },

    # ======== 4. BGP 路由器故障 (6种, simple_bgp) ======== #
    {
        "fault_name": "bgp_neighbor_shutdown",
        "deploy_query": "创建一个跨域的 BGP 路由网络",
        "fault_query": "将 BGP 邻居 administratively shutdown"
    },
    {
        "fault_name": "bgp_withdraw_route",
        "deploy_query": "部署 simple_bgp 场景",
        "fault_query": "撤销 BGP 路由器上的业务网段宣告"
    },
    {
        "fault_name": "bgp_wrong_peer_asn",
        "deploy_query": "我要测试 BGP 协议",
        "fault_query": "把 BGP 邻居的对端 AS 号配错"
    },
    {
        "fault_name": "acl_blocking_bgp_traffic",
        "deploy_query": "启动 BGP 实验网络",
        "fault_query": "用防火墙阻断 BGP 的 TCP 179 端口"
    },
    {
        "fault_name": "bgp_local_pref_spike",
        "deploy_query": "部署 simple_bgp 网络",
        "fault_query": "通过 route-map 异常调高 Local Preference 属性"
    },
    {
        "fault_name": "bgp_med_spike",
        "deploy_query": "建立 BGP 测试拓扑",
        "fault_query": "给发往邻居的路由加上极高的 MED 值"
    },

    # ======== 5. OSPF 路由器故障 (7种, ospf_enterprise) ======== #
    {
        "fault_name": "ospf_passive_interface",
        "deploy_query": "部署一个企业级 OSPF 动态路由网络",
        "fault_query": "把互联接口设置为 OSPF 被动接口"
    },
    {
        "fault_name": "ospf_cost_spike",
        "deploy_query": "我要 ospf_enterprise 场景",
        "fault_query": "将某条核心链路的 OSPF 开销(cost)改为 65000"
    },
    {
        "fault_name": "ospf_daemon_crash",
        "deploy_query": "启动 OSPF 企业网仿真",
        "fault_query": "强制杀掉 ospfd 进程"
    },
    {
        "fault_name": "acl_blocking_ospf_traffic",
        "deploy_query": "我要测试 OSPF 协议",
        "fault_query": "使用 iptables 拦截 OSPF (协议号89) 报文"
    },
    {
        "fault_name": "ospf_neighbor_misconfig",
        "deploy_query": "部署 OSPF 网络",
        "fault_query": "把两台路由器的 Hello 定时器改成不一致"
    },
    {
        "fault_name": "ospf_area_misconfig",
        "deploy_query": "我要企业级 OSPF 拓扑",
        "fault_query": "把接口错误宣告到 Area 99"
    },
    {
        "fault_name": "ospf_auth_misconfig",
        "deploy_query": "启动 ospf_enterprise",
        "fault_query": "在一端开启 OSPF MD5 认证配个错误密码"
    },

    # ======== 6. RIP 路由器故障 (7种, rip_internet) ======== #
    {
        "fault_name": "rip_passive_interface",
        "deploy_query": "部署一个中小型的 RIP 路由网络",
        "fault_query": "配置 RIP passive-interface 让接口变静默"
    },
    {
        "fault_name": "rip_route_filter",
        "deploy_query": "我要 rip_internet 场景",
        "fault_query": "用 distribute-list 过滤掉发出的 RIP 路由"
    },
    {
        "fault_name": "rip_metric_offset",
        "deploy_query": "启动 RIP 协议测试",
        "fault_query": "用 offset-list 把路由跳数(metric)增加 15"
    },
    {
        "fault_name": "acl_blocking_rip_traffic",
        "deploy_query": "我要中小型企业 RIP 网络",
        "fault_query": "在入方向 DROP 掉 UDP 520 端口的流量"
    },
    {
        "fault_name": "rip_version_mismatch",
        "deploy_query": "部署 rip_internet",
        "fault_query": "强制把运行版本改成 RIP version 1 制造错配"
    },
    {
        "fault_name": "rip_timer_misconfig",
        "deploy_query": "创建一个 RIP 网络",
        "fault_query": "把 RIP 的基础计时器全部改成 999 秒"
    },
    {
        "fault_name": "rip_network_withdraw",
        "deploy_query": "我要 RIP 动态网络",
        "fault_query": "在路由进程里撤销宣告某个直连网段"
    },

    # ======== 7. P4 交换机故障 (5种, p4_star) ======== #
    {
        "fault_name": "p4_bmv2_process_crash",
        "deploy_query": "部署一个可编程数据面 P4 星型网络",
        "fault_query": "杀掉 bmv2 交换机的 simple_switch 进程"
    },
    {
        "fault_name": "p4_table_drop",
        "deploy_query": "我要 p4_star 拓扑",
        "fault_query": "把某条路由表项的动作改成 drop"
    },
    {
        "fault_name": "p4_wrong_forwarding",
        "deploy_query": "启动 P4 可编程网络",
        "fault_query": "篡改表项，把转发端口改成不存在的端口(比如 99)"
    },
    {
        "fault_name": "p4_table_entry_missing",
        "deploy_query": "我要测试 bmv2 交换机",
        "fault_query": "删掉匹配某台主机的 P4 转发表项"
    },
    {
        "fault_name": "p4_default_action_drop",
        "deploy_query": "部署 p4_star 场景",
        "fault_query": "将转发表的默认动作(default action)设置为 drop"
    },

    # ======== 8. SDN 交换机/控制器故障 (8种, sdn_openflow) ======== #
    {
        "fault_name": "sdn_controller_crash",
        "deploy_query": "部署一个包含 Ryu 控制器的 SDN 网络",
        "fault_query": "杀掉 Ryu 控制器进程"
    },
    {
        "fault_name": "ovs_disconnect",
        "deploy_query": "我要 sdn_openflow 场景",
        "fault_query": "在交换机上 del-controller 断开控制器连接"
    },
    {
        "fault_name": "ovs_global_drop",
        "deploy_query": "启动 SDN 实验环境",
        "fault_query": "下发一条优先级为 65535 的全局丢弃(drop)流表"
    },
    {
        "fault_name": "southbound_wrong_controller",
        "deploy_query": "我要跑 OVS 和 Ryu 的拓扑",
        "fault_query": "把 OVS 连向控制器的地址改成个错的 IP"
    },
    {
        "fault_name": "southbound_protocol_mismatch",
        "deploy_query": "部署 sdn_openflow",
        "fault_query": "强制把 OVS 南向协议降级成 OpenFlow10"
    },
    {
        "fault_name": "flow_rule_shadowing",
        "deploy_query": "创建一个 OpenFlow 软件定义网络",
        "fault_query": "注入一条高优先级 normal 动作流表，覆盖精细策略"
    },
    {
        "fault_name": "flow_rule_loop",
        "deploy_query": "我要 sdn_openflow 网络",
        "fault_query": "下发一条让流量从原端口直接打回的自环流表"
    },
    {
        "fault_name": "ovs_fail_secure",
        "deploy_query": "启动 SDN 拓扑",
        "fault_query": "把 OVS 的 fail-mode 设置为 secure"
    },

    # ======== 9. AI 推理服务故障 (6种, ai_inference) ======== #
    {
        "fault_name": "ai_service_crash",
        "deploy_query": "部署一个包含算力节点的 AI 推理 Spine-Leaf 网络",
        "fault_query": "直接终止算力节点上的 python3 推理进程"
    },
    {
        "fault_name": "compute_cpu_starvation",
        "deploy_query": "我要 ai_inference 场景",
        "fault_query": "用 stress-ng 把 AI 节点的 CPU 打满"
    },
    {
        "fault_name": "compute_memory_exhaustion",
        "deploy_query": "建立端到端大模型推理网络",
        "fault_query": "消耗掉算力服务器 95% 的内存"
    },
    {
        "fault_name": "inference_port_blocked",
        "deploy_query": "我要测试 AI 推理业务",
        "fault_query": "在服务端用防火墙拦截 TCP 8000 端口"
    },
    {
        "fault_name": "tcp_rst_injection",
        "deploy_query": "部署 ai_inference 拓扑",
        "fault_query": "在中间路由器注入 TCP 重置(RST) 报文"
    },
    {
        "fault_name": "cross_layer_traffic_blackhole",
        "deploy_query": "我要测试ai算网融合网络",
        "fault_query": "在中间节点针对业务目的端口做静默丢弃(DROP)，导致算网隔离"
    }
]