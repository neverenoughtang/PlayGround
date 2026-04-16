from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class OSPFRouting(NetworkEnvBase):
    """
    OSPF分层网络场景 (规模扩容): Core(3) -> Dist(4) -> Access(4) -> Host(8) + Servers(4) (共 24 节点)
    """
    def __init__(self, lab_name="ospf_enterprise"):
        super().__init__(lab_name=lab_name)

        # --- 1. 创建节点 ---
        # 1.1 核心层 (Core)
        cores = [self.lab.add_node(f"c{i}", self.lab.images["quagga"], x=300+150*i, y=200) for i in range(1, 4)]
        
        # 1.2 服务区块 (Service Block)
        s_sw = self.lab.add_node("ssw", self.lab.images["ovs"], x=500, y=100) 
        servers = [self.lab.add_node(name, self.lab.images["new_ubuntu"], x=400+60*i, y=50) for i, name in enumerate(["dns", "dhcp", "lb", "db"])]

        # 1.3 汇聚层 (Distribution)
        dists = [self.lab.add_node(f"d{i}", self.lab.images["quagga"], x=200+200*i, y=350) for i in range(1, 5)]

        # 1.4 接入层 (Access)
        accesses = [self.lab.add_node(f"a{i}", self.lab.images["ovs"], x=200+200*i, y=500) for i in range(1, 5)]

        # 终端主机 (8台)
        hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=150+100*i, y=600) for i in range(1, 9)]

        # --- 2. 创建链路 ---
        # 核心环网
        self.lab.add_link(cores[0], cores[1]); self.lab.add_link(cores[1], cores[2]); self.lab.add_link(cores[2], cores[0])
        
        # 服务区接入
        self.lab.add_link(cores[1], s_sw)
        for srv in servers: self.lab.add_link(s_sw, srv)

        # 核心下联汇聚 (交叉冗余)
        self.lab.add_link(cores[0], dists[0]); self.lab.add_link(cores[1], dists[0])
        self.lab.add_link(cores[0], dists[1]); self.lab.add_link(cores[1], dists[1])
        self.lab.add_link(cores[1], dists[2]); self.lab.add_link(cores[2], dists[2])
        self.lab.add_link(cores[1], dists[3]); self.lab.add_link(cores[2], dists[3])

        # 汇聚下联接入 (单线)
        for i in range(4): self.lab.add_link(dists[i], accesses[i])

        # 接入下联主机 (每个接入连2台)
        for i in range(4):
            self.lab.add_link(accesses[i], hosts[i*2])
            self.lab.add_link(accesses[i], hosts[i*2+1])

        # 3. 部署与自动配置
        self.deploy()
        time.sleep(20)

        # 4. 配置 OSPF
        self.config(senario="ospf")
        time.sleep(15)

if __name__ == "__main__":
    Lab_OSPF = OSPFRouting()
    print("--- 测试跨区域通信: H1 -> H8 ---")
    print(Lab_OSPF.lab.ping_pair("h1", "h8"))
    print("--- 测试 H1 -> DNS Server ---")
    print(Lab_OSPF.lab.ping_pair("h1", "dns"))