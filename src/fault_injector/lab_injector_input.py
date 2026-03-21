# 记录每个场景的主机故障输入参数(字典)
HOST_INJECT_INPUT = {
    "static_routing": {
        "lab": "static_routing", 
        "target": "h1", 
        "iface": "tos1_1", 
        "target_ip": "192.168.1.1", # arp 投毒对象: h1 的网关
        "origin_ip": "192.168.1.2/24", 
        "wrong_ip": "10.0.0.0/24", 
        "wrong_mac": "aa:bb:cc:dd:ee:ff",
        "gateway": "192.168.1.254", 
        "peer_ip_same_subnet": "192.168.1.3", 
        "peer_ip_cross_subnet": "192.168.4.2"
    },
    "simple_bgp": {
        "lab": "simple_bgp", 
        "target": "h2", 
        "iface": "tor2_1", 
        "origin_ip": "192.168.3.2/24", 
        "wrong_ip": "10.0.0.0/24", 
        "wrong_mac": "dd:aa:bb:ef:00:00",
        "gateway": "192.168.3.1", 
        "peer_ip_same_subnet": "192.168.4.2", 
        "peer_ip_cross_subnet": "192.168.2.2"
    },
    "ospf_enterprise": {
        "lab": "ospf_enterprise", 
        "target": "h1", 
        "iface": "tod1_1", 
        "origin_ip": "192.168.7.2/24", 
        "wrong_ip": "10.0.0.0/24", 
        "wrong_mac": "aa:bb:cc:dd:ee:ff",
        "gateway": "192.168.7.1", 
        "peer_ip_same_subnet": "192.168.7.3", 
        "peer_ip_cross_subnet": "192.168.3.2"
    },
    "rip_internet": {
        "lab": "rip_internet", 
        "target": "pc1", 
        "iface": "tor1_1", 
        "origin_ip": "192.168.0.2/24", 
        "wrong_ip": "10.0.0.0/24", 
        "wrong_mac": "11:22:33:44:55:66",
        "gateway": "192.168.0.1", 
        "peer_ip_same_subnet": "192.168.0.3", 
        "peer_ip_cross_subnet": "192.168.4.2"
    },
    "sdn_openflow": {
        "lab": "sdn_openflow", 
        "target": "h1", 
        "iface": "tos1_1", 
        "origin_ip": "10.0.0.1/24", 
        "wrong_ip": "192.168.1.1/24", 
        "wrong_mac": "cc:cc:cc:dd:dd:dd",
        "gateway": "10.0.0.254", 
        "peer_ip_same_subnet": "10.0.0.2", 
        "peer_ip_cross_subnet": "10.0.0.3"
    },
    "p4_star": {
        "lab": "p4_star", 
        "target": "h1", 
        "iface": "tos1_1", 
        "origin_ip": "10.0.0.1/24", 
        "wrong_ip": "192.168.1.1/24", 
        "wrong_mac": "bb:bb:bb:aa:aa:aa",
        "gateway": "10.0.0.254", 
        "peer_ip_same_subnet": "10.0.0.3", 
        "peer_ip_cross_subnet": "10.0.0.2"
    }
}

LINK_INJECT_INPUT = {
    "static_routing": {
        "lab": "static_routing", "host": "h1", "peer_host": "h2", "link_id": "l6"
    },
    "simple_bgp": {
        "lab": "simple_bgp", "host": "h1", "peer_host": "h2", "link_id": "l3"
    },
    "ospf_enterprise": {
        "lab": "ospf_enterprise", "host": "h1", "peer_host": "h2", "link_id": "l14"
    },
    "rip_internet": {
        "lab": "rip_internet", "host": "pc1", "peer_host": "pc4", "link_id": "l6"
    },
    "sdn_openflow": {
        "lab": "sdn_openflow", "host": "h1", "peer_host": "h3", "link_id": "l1"
    },
    "p4_star": {
        "lab": "p4_star", "host": "h1", "peer_host": "h2", "link_id": "l1"
    }
}

SERVICE_INJECT_INPUT = {
    "static_routing": {
        "script": "static_routing.py",
        "lab": "static_routing", 
        "router": "r1",
        "blackhole_net": "192.168.4.0/24",
        "host_src": "h1",
        "dst_ip": "192.168.4.2"  # 显式指定目标 IP (h4)
    },
    "simple_bgp": {
        "script": "simple_bgp.py",
        "lab": "simple_bgp",
        "router": "r1",
        "asn": 65001,                   # [修复] 真实的本地 ASN
        "neighbor_ip": "192.168.0.2",   # [修复] 真实的邻居 IP (r2)
        "wrong_asn": 999,
        "withdraw_net": "192.168.2.0/24", # [修复] r1 宣告的是 h1 的网段
        "host_src": "h1",
        "dst_ip": "192.168.3.2"         # [修复] 跨越 BGP 的目标 IP (h2)
    },
    "ospf_enterprise": {
        "script": "ospf_enterprise.py",
        "lab": "ospf_enterprise",
        "router": "c1",                  # [修复] 真实节点名是 c1
        "passive_iface": "toc2_1",       # [修复] 假设阻断 c1 连向 c2 的 OSPF 接口
        "host_src": "h1",
        "dst_ip": "192.168.8.2"          # 目标 IP 保持不变
    },
    "rip_internet": {
        "script": "rip_internet.py",
        "lab": "rip_internet",
        "router": "r4",                  # [修复] 真实节点名是小写 r4
        "withdraw_net": "192.168.4.0/24", 
        "passive_iface": "tor3_1",       # [修复] r4 连向骨干网 r3 的接口
        "host_src": "pc1",
        "dst_ip": "192.168.5.2"          # pc4 的 IP
    },
    "sdn_openflow": {
        "script": "sdn_openflow.py",
        "lab": "sdn_openflow",
        "controller": "controller",    # Ryu 控制器节点名
        "switch": "s1",                # OVS 交换机名
        "host_src": "h1",
        "dst_ip": "10.0.0.3"           # 目标主机 IP (请根据拓扑实际情况确认，通常为 10.0.0.x)
    },
    "p4_star": {
        "script": "p4_star.py",
        "lab": "p4_star",
        "switch": "s1",                # P4 交换机名
        "table": "MyIngress.ipv4_lpm", # P4 表名
        "drop_ip": "10.0.0.2/32",      # P4 程序中配置的丢弃规则 IP
        "wrong_port": "99",            # [修复] 假设丢弃规则中端口号错误
        "host_src": "h1",              # [修复] 假设源主机 IP 错误
        "host_dst": "h2"               # 目的主机
    }
}