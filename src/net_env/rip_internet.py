from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class RIPInternet(NetworkEnvBase):
    """
    RIP 网络场景 (规模扩容): GW(1) + Routers(6) + Servers(2) + PCs(12) (共 21 节点)
    """
    def __init__(self, lab_name="rip_internet"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        gw = self.lab.add_node("gw", self.lab.images["quagga"], x=50, y=400)
        routers = [self.lab.add_node(f"r{i}", self.lab.images["quagga"], x=200+150*i, y=400) for i in range(1, 7)]
        
        servers = [self.lab.add_node(f"server{i}", self.lab.images["new_ubuntu"], x=50, y=200+100*i) for i in range(1, 3)]
        pcs = [self.lab.add_node(f"pc{i}", self.lab.images["new_ubuntu"], x=200+100*i, y=600) for i in range(1, 13)]

        # 2. 创建链路
        # GW 连接 Servers
        self.lab.add_link(gw, servers[0]); self.lab.add_link(gw, servers[1])
        
        # 骨干网串联 & 冗余
        self.lab.add_link(gw, routers[0])
        for i in range(5): self.lab.add_link(routers[i], routers[i+1])
        self.lab.add_link(routers[1], routers[3]); self.lab.add_link(routers[3], routers[5])

        # PC 接入 (R1-R6 每台挂2台PC)
        for i in range(6):
            self.lab.add_link(routers[i], pcs[i*2])
            self.lab.add_link(routers[i], pcs[i*2+1])

        # 3. 部署与自动配置
        self.deploy()
        time.sleep(20)

        # 强制开启 IP Forwarding
        for r in ["gw"] + [f"r{i}" for i in range(1, 7)]:
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")

        # 4. 配置 RIP
        self.config(senario="rip")
        time.sleep(15)

if __name__ == "__main__":
    Lab_RIP = RIPInternet()
    print("\n--- 🔍 路由表诊断 (R3) ---")
    print(Lab_RIP.lab.execute("r3", "ip route"))

    print("\n--- 正式测试 PC1 -> PC12 连通性 ---")
    print(Lab_RIP.lab.ping_pair("pc1", "pc12"))