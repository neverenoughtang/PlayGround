# simple_bgp_balanced.py
from dotenv import load_dotenv
load_dotenv() 
import time

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class BGPRoutingBalanced(NetworkEnvBase):
    """
    BGP 网络场景 - 黄金比例胖树 / Clos 拓扑
    
    架构说明 (14 节点, 16 链路)：
    - Core/Spine 层 (2台): r1, r2
    - Edge/ToR 层 (4台): r3, r4, r5, r6
    - Host 层 (8台): h1~h8
    """
    def __init__(self, lab_name="simple_bgp"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 创建节点
        # ==========================================
        # Core 层 (X轴居中，Y轴在顶部)
        cores = [
            self.lab.add_node("r1", self.lab.images["quagga"], x=300, y=100),
            self.lab.add_node("r2", self.lab.images["quagga"], x=500, y=100),
        ]

        # Edge / ToR 层 (展开分布)
        edges = [
            self.lab.add_node("r3", self.lab.images["quagga"], x=200, y=300),
            self.lab.add_node("r4", self.lab.images["quagga"], x=400, y=300),
            self.lab.add_node("r5", self.lab.images["quagga"], x=600, y=300),
            self.lab.add_node("r6", self.lab.images["quagga"], x=800, y=300),
        ]

        # 主机层 (每台 ToR 挂载 3 台，共 12 台)
        hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=50+60*i, y=500) for i in range(1, 13)]

        # ==========================================
        # 2. 创建胖树全互联链路 (16条子网，平台安全范围内)
        # ==========================================
        # 核心层 -> 接入层 (2 * 4 = 8 条链路)
        for core in cores:
            for edge in edges:
                self.lab.add_link(core, edge)
        
        # 接入层 -> 主机层 (4 * 3 = 12 条链路)
        # R3 -> H1, H2, H3
        self.lab.add_link(edges[0], hosts[0]); self.lab.add_link(edges[0], hosts[1]); self.lab.add_link(edges[0], hosts[2])
        # R4 -> H4, H5, H6
        self.lab.add_link(edges[1], hosts[3]); self.lab.add_link(edges[1], hosts[4]); self.lab.add_link(edges[1], hosts[5])
        # R5 -> H7, H8, H9
        self.lab.add_link(edges[2], hosts[6]); self.lab.add_link(edges[2], hosts[7]); self.lab.add_link(edges[2], hosts[8])
        # R6 -> H10, H11, H12
        self.lab.add_link(edges[3], hosts[9]); self.lab.add_link(edges[3], hosts[10]); self.lab.add_link(edges[3], hosts[11])

        # ==========================================
        # 3. 部署与底层防崩溃调优
        # ==========================================
        print("[System] 🚀 正在下发黄金比例胖树拓扑 (14 节点)...")
        self.deploy()
        time.sleep(20) 

        print("[System] 🛡️ 正在注入 Linux 内核网络防冲突规则...")
        for r in [f"r{i}" for i in range(1, 7)]:
            # 开启转发，彻底关闭反向路径过滤 (解决多路径 ECMP 丢包)
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")
            self.lab.execute(r, "sysctl -w net.ipv4.conf.all.rp_filter=0")
            self.lab.execute(r, "sysctl -w net.ipv4.conf.default.rp_filter=0")
            self.lab.execute(r, "iptables -F")
            
            # 关闭硬件校验和卸载，杜绝 TCP 握手被静默丢弃
            self.lab.execute(r, "for intf in $(ls /sys/class/net/ | grep -v lo); do ip link set $intf up mtu 1400; ethtool -K $intf tx off rx off 2>/dev/null; done")
            # 预热 ARP 表，防止初始握手超时
            self.lab.execute(r, "for intf in $(ls /sys/class/net/ | grep -v lo); do ping -c 1 -I $intf -b 255.255.255.255 2>/dev/null & done")

        # ==========================================
        # 4. 自动配置与【步进式】启动
        # ==========================================
        print("[System] ⚙️ 请求 Klonet 自动分配全局 IP 与 BGP 配置...")
        self.config(senario="bgp")
        
        print("[System] 🧹 暴力清理僵尸进程...")
        for r in [f"r{i}" for i in range(1, 7)]:
            self.lab.execute(r, "killall -9 zebra bgpd 2>/dev/null")
            self.lab.execute(r, "rm -f /var/run/quagga/*.pid")
        
        print("[System] 🦓 阶段 1：启动 Zebra 路由底座...")
        for r in [f"r{i}" for i in range(1, 7)]:
            self.lab.execute(r, "/etc/init.d/zebra start")
            
        time.sleep(3)
        
        print("[System] 🦅 阶段 2：错峰启动 BGP 服务...")
        for r in [f"r{i}" for i in range(1, 7)]:
            self.lab.execute(r, "/etc/init.d/bgpd start")
            time.sleep(1) # R1 到 R6 逐个唤醒，避免 Netlink 拥塞
            
        print("[System] ⏳ 等待全网 20 个 BGP Session 完成状态机收敛...")
        time.sleep(30)


# ==========================================
# 解析函数 (精准剥离嵌套结构)
# ==========================================
def get_cmd_output(node_name, response_dict):
    if not isinstance(response_dict, dict): 
        return str(response_dict).strip()
    node_data = response_dict.get(node_name)
    if not node_data: return ""
    for key, val in node_data.items():
        if isinstance(val, dict) and 'output' in val:
            return val['output'].strip()
    return str(node_data).strip()


if __name__ == "__main__":
    Lab_BGP = BGPRoutingBalanced()

    print("\n" + "="*50)
    print(" 🛠️  胖树 BGP 深度检验报告 (6 Router x 8 Host)")
    print("="*50)

    # 1. 验证两端边缘主机的 IP 
    h1_ip = get_cmd_output("h1", Lab_BGP.lab.execute("h1", "hostname -I")).split()[0]
    h12_ip = get_cmd_output("h12", Lab_BGP.lab.execute("h12", "hostname -I")).split()[0]
    print(f"[*] 最左侧边缘主机 H1 IP: {h1_ip}")
    print(f"[*] 最右侧边缘主机 H12 IP: {h12_ip}")

    # 2. 检查核心 R1 的 BGP 状态 (期望看到 4 个邻居 r3, r4, r5, r6，全为数字 Established)
    print("\n[*] 核心层 R1 BGP 邻居状态 (期望 4 个 Active 邻居):")
    r1_bgp = Lab_BGP.lab.execute("r1", 'vtysh -c "show ip bgp summary"')
    print(get_cmd_output("r1", r1_bgp))

    # 3. 检查边缘 ToR R6 的 BGP 状态 (期望看到 2 个邻居 r1, r2)
    print("\n[*] 接入层 R6 BGP 邻居状态 (期望 2 个向上邻居):")
    r6_bgp = Lab_BGP.lab.execute("r6", 'vtysh -c "show ip bgp summary"')
    print(get_cmd_output("r6", r6_bgp))

    # 4. 路由表检查
    print("\n[*] 核心层 R1 的全网路由表 (检查 ECMP 多路径负载):")
    r1_route = Lab_BGP.lab.execute("r1", "ip route")
    print(get_cmd_output("r1", r1_route))

    # 5. 端到端极限 Ping 测试 (加上 -A 和包大小测试真实环境)
    print(f"\n[*] 发起世纪连通性测试: H1 -> H12 ({h12_ip}) (跨越 R3 -> R1/R2 -> R6)")
    ping_res = Lab_BGP.lab.execute("h1", f"ping -c 4 -W 2 -s 1000 {h12_ip}")
    print(get_cmd_output("h1", ping_res))