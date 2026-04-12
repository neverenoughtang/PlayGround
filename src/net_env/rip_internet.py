from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class RIPInternet(NetworkEnvBase):
    """
    RIP 网络场景: 模拟小型互联网 Stub 网络
    拓扑结构:
    GW --- R4 --- R3 --- R1 --- Server
                  |      |
                  R2 ----+
    (PC 接在各路由器下)
    """
    def __init__(self, lab_name="rip_internet"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        # 核心路由区域 (RIP Domain)
        r1 = self.lab.add_node("r1", self.lab.images["quagga"], x=600, y=300)
        r2 = self.lab.add_node("r2", self.lab.images["quagga"], x=600, y=500)
        r3 = self.lab.add_node("r3", self.lab.images["quagga"], x=400, y=400)
        r4 = self.lab.add_node("r4", self.lab.images["quagga"], x=200, y=400)
        
        # 网关路由器
        gw = self.lab.add_node("gw", self.lab.images["quagga"], x=50, y=400)

        # 终端设备 (PC & Server)
        pc1 = self.lab.add_node("pc1", self.lab.images["new_ubuntu"], x=750, y=300)
        server = self.lab.add_node("server", self.lab.images["new_ubuntu"], x=750, y=200) # R1 旁挂服务器
        pc2 = self.lab.add_node("pc2", self.lab.images["new_ubuntu"], x=750, y=500)
        pc3 = self.lab.add_node("pc3", self.lab.images["new_ubuntu"], x=400, y=550)
        pc4 = self.lab.add_node("pc4", self.lab.images["new_ubuntu"], x=200, y=550)

        # 2. 创建链路
        # 路由器互联 (骨干网)
        self.lab.add_link(gw, r4, link_name="link_gw_r4")
        self.lab.add_link(r4, r3, link_name="link_r4_r3")
        
        # RIP 域内三角互联
        self.lab.add_link(r3, r1, link_name="link_r3_r1")
        self.lab.add_link(r3, r2, link_name="link_r3_r2")
        self.lab.add_link(r1, r2, link_name="link_r1_r2")

        # 终端接入链路
        self.lab.add_link(r1, pc1)
        self.lab.add_link(r1, server)
        self.lab.add_link(r2, pc2)
        self.lab.add_link(r3, pc3)
        self.lab.add_link(r4, pc4)

        # 3. 部署与自动配置
        self.deploy()

        # 等待 Quagga 进程启动 (RIP 需要时间建立邻居)
        time.sleep(20)

        # 强制开启 IP Forwarding
        routers = ["gw", "r1", "r2", "r3", "r4"]
        for r in routers:
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")

        # 4. 调用全局自动配置API
        self.config(senario="rip")

        # 等待 RIP 路由收敛
        time.sleep(15)

if __name__ == "__main__":
    Lab_RIP = RIPInternet()

    print("\n--- 🔍 路由表诊断 (R1) ---")
    # 检查 R1 是否学到了去往 GW 或 R4 的路由
    route_info = Lab_RIP.lab.execute("r1", "ip route")
    print(route_info)

    # --- 开始正式测试 ---
    print("\n--- 正式测试 PC1 -> PC4 连通性 ---")
    ping_res = Lab_RIP.lab.ping_pair("pc1", "pc4")
    print(ping_res)