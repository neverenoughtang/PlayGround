DOMAIN_WORDS = [
    # --- 核心协议与技术名词 ---
    "OSPF", "BGP", "RIP", "P4", "SDN", "OVS", "OpenFlow", "FRR", "BMv2", "ICMP", "ARP", "DNS", 
    "Spine-Leaf", "underlay", "TCP", "UDP", "Ryu", "thrift", "AI", "inference"
    
    # --- 中文故障现象与网络黑话 (极易被错误分词) ---
    "链路丢包", "链路延迟", "链路抖动", "带宽限制", "严重卡顿", "延迟极高", "忽快忽慢", "网络拥塞", 
    "IP错配", "地址丢失", "地址不一致", "掩码错误", "默认路由缺失", "跨网段", "彻底脱网", "ARP投毒", 
    "伪造MAC", "端口耗尽", "路由缺失", "黑洞路由", "有去无回", "神秘丢弃", "进程宕机", "局部瘫痪", 
    "网关漂移", "邻接关系", "邻居异常", "邻居关闭", "撤销宣告", "异常升高", "路径绕行", "流量切换", 
    "接口静默", "开销突增", "重收敛", "进程崩溃", "邻居错配", "区域错配", "认证错配", "路由过滤", 
    "学不到路由", "度量值篡改", "版本错配", "计时器篡改", "路由撤销", "引擎崩溃", "表项缺失", 
    "默认动作", "全局阻断", "控制面断连", "协议错配", "流表覆盖", "策略失效", "自回环", "流表环路", 
    "死循环", "兜底转发", "算力节点", "服务节点", "中间转发", "算网隔离", "跨层黑洞", "推理崩溃", "推理慢", 
    "CPU满载", "内存溢出", "吐字极慢", "大并发无响应", "端口阻断", "连接拒绝", "连接被重置", "网关可达",

    # --- 英文配置参数与关键命令行回显 ---
    "passive-interface", "netem", "qdisc", "tbf", "resolv.conf", "nameserver", "stress-ng",
    "stress-ng-cpu", "stress-ng-vm", "default via", "state DOWN", "blackhole", "zebra", "bgpd",
    "ospfd", "vtysh", "remote-as", "route-map", "localpref", "metric", "distribute-list",
    "offset-list", "BadPackets", "simple_switch", "ipv4_lpm", "ryu-manager", "ovs-vsctl",
    "ovs-ofctl", "fail_mode", "tcp-reset", "REJECT", "Established", "Idle", "Active",
    "Connection Refused", "unreachable", "Network unreachable",

    # --- 故障注入代码中的核心英文 Label (如果 Agent 也需要检索这些) ---
    "link_loss", "link_latency", "link_jitter", "link_bandwidth", "ip_misconfig", 
    "default_route_missing", "arp_poisoning", "interface_down", "dns_error", "cpu_overload", 
    "routing_error", "mask_error", "host_port_exhaustion", "route_missing", "static_route_blackhole", 
    "data_plane_drop", "frr_service_down", "ip_forward_disabled", "router_interface_ip_wrong", 
    "bgp_neighbor_shutdown", "bgp_withdraw_route", "bgp_wrong_peer_asn", "acl_blocking_bgp_traffic", 
    "bgp_local_pref_spike", "bgp_med_spike", "ospf_passive_interface", "ospf_cost_spike", 
    "ospf_daemon_crash", "acl_blocking_ospf_traffic", "ospf_neighbor_misconfig", "ospf_area_misconfig", 
    "ospf_auth_misconfig", "rip_passive_interface", "rip_route_filter", "rip_metric_offset", 
    "acl_blocking_rip_traffic", "rip_version_mismatch", "rip_timer_misconfig", "rip_network_withdraw", 
    "p4_bmv2_process_crash", "p4_table_drop", "p4_wrong_forwarding", "p4_table_entry_missing", 
    "p4_default_action_drop", "sdn_controller_crash", "ovs_disconnect", "ovs_global_drop", 
    "southbound_wrong_controller", "southbound_protocol_mismatch", "flow_rule_shadowing", 
    "flow_rule_loop", "ovs_fail_secure", "ai_service_crash", "compute_cpu_starvation", 
    "compute_memory_exhaustion", "inference_port_blocked", "tcp_rst_injection", "cross_layer_traffic_blackhole"
]