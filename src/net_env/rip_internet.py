from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class RIPInternet(NetworkEnvBase):
    """
    RIP 网络场景 - 简化两层架构（修复版）
    
    架构说明：
    - 互联网网关（GW）：1 台路由器 (gw)，作为整个网络的出口
    - 区域路由器（Regional）：4 台路由器 (r1, r2, r3, r4)，环形互联
    - 服务器（Server）：2 台服务器 (server1, server2)，直连 GW
    - 客户端（PC）：12 台客户端 (pc1-pc12)，每台区域路由器连接 3 台
    
    总计：5 台路由器 + 2 台服务器 + 12 台 PC = 19 节点
    
    拓扑结构：
    ```
         [server1]  [server2]
              \\     /
               \\   /
                [gw]  (互联网网关)
                 |
            +----+----+----+
            |    |    |    |
          [r1] [r2] [r3] [r4]  (区域路由器，环形互联)
           |||  |||  |||  |||
         pc1-3 pc4-6 pc7-9 pc10-12 (客户端，每台路由器连 3 台)
    ```
    
    设计改进：
    - 去除接入层，简化为两层架构（网关+区域）
    - 减少路由器数量（从 7 台降至 5 台）
    - 保持主机数量为 12 台（符合要求）
    - 区域路由器环形互联，提供冗余路径
    """
    def __init__(self, lab_name="rip_internet"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 创建节点（分层创建）
        # ==========================================
        
        # 互联网网关（1 台）
        gw = self.lab.add_node("gw", self.lab.images["quagga"], x=400, y=50)
        
        # 服务器（2 台，直连网关）
        servers = [
            self.lab.add_node("server1", self.lab.images["new_ubuntu"], x=250, y=50),
            self.lab.add_node("server2", self.lab.images["new_ubuntu"], x=550, y=50)
        ]
        
        # 区域路由器（4 台）
        regional_routers = [
            self.lab.add_node("r1", self.lab.images["quagga"], x=150, y=250),
            self.lab.add_node("r2", self.lab.images["quagga"], x=350, y=250),
            self.lab.add_node("r3", self.lab.images["quagga"], x=550, y=250),
            self.lab.add_node("r4", self.lab.images["quagga"], x=750, y=250)
        ]
        
        # 客户端（12 台，每台区域路由器连接 3 台）
        pcs = []
        for i in range(4):  # 4 台区域路由器
            for j in range(3):  # 每台连 3 台 PC
                pc_id = i * 3 + j + 1  # pc1-pc12
                x_pos = 100 + i * 200 + j * 50  # 水平分布
                y_pos = 450
                pcs.append(
                    self.lab.add_node(f"pc{pc_id}", self.lab.images["new_ubuntu"], x=x_pos, y=y_pos)
                )

        # ==========================================
        # 2. 创建链路
        # ==========================================
        
        # 网关层：GW 连接服务器
        self.lab.add_link(gw, servers[0])  # gw - server1
        self.lab.add_link(gw, servers[1])  # gw - server2
        
        # 核心层：GW 连接所有区域路由器（星形）
        for r in regional_routers:
            self.lab.add_link(gw, r)
        
        # 区域层：区域路由器环形互联（提供冗余）
        for i in range(4):
            # 每台路由器连接下一台（r1-r2, r2-r3, r3-r4, r4-r1）
            next_router = regional_routers[(i + 1) % 4]
            self.lab.add_link(regional_routers[i], next_router)
        
        # 终端层：区域路由器连接 PC（每台 3 个）
        for i in range(4):  # 4 台区域路由器
            for j in range(3):  # 每台连 3 台 PC
                pc_idx = i * 3 + j
                self.lab.add_link(regional_routers[i], pcs[pc_idx])

        # ==========================================
        # 3. 部署与自动配置
        # ==========================================
        self.deploy()
        time.sleep(25)  # 等待容器启动

        # 强制开启所有路由器的 IP Forwarding
        all_routers = ["gw", "r1", "r2", "r3", "r4"]
        for r in all_routers:
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")

        # 4. 配置 RIP
        self.config(senario="rip")
        time.sleep(15)


if __name__ == "__main__":
    Lab_RIP = RIPInternet()

    # 1. gw 路由表（不使用管道，Python 自己过滤）
    print("\n--- 🔍 路由表诊断 (gw 网关) ---")
    result = Lab_RIP.lab.execute("gw", "ip route")
    output = result['gw']['0_ip route']['output']
    routes = [line for line in output.split('\n') if line.startswith('192.168')]
    print(f"gw 学习到的路由条目数: {len(routes)}")
    for r in routes[:5]:  # 只打印前 5 条
        print(f"  {r}")

    # 2. r1 路由表
    print("\n--- 🔍 路由表诊断 (r1 接入路由器) ---")
    result = Lab_RIP.lab.execute("r1", "ip route")
    output = result['r1']['0_ip route']['output']
    print(f"r1 路由表:\n{output}")

    # 3. r2 RIP 状态
    print("\n--- 🔍 RIP 状态 (r2 区域路由器) ---")
    print(Lab_RIP.lab.execute("r2", 'vtysh -c "show ip rip status"'))

    # 4. 连通性测试
    print("\n--- 测试 pc1 -> pc12 连通性（跨越整个网络）---")
    print(Lab_RIP.lab.ping_pair("pc1", "pc12"))

    print("\n--- 测试 pc1 -> server1 连通性（终端到服务器）---")
    print(Lab_RIP.lab.ping_pair("pc1", "server1"))

    print("\n--- 测试 pc4 -> server2 连通性（验证 r5 域）---")
    print(Lab_RIP.lab.ping_pair("pc4", "server2"))