from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class BGPRouting(NetworkEnvBase):
    """
    BGP网络场景 (规模扩容): 5 Router 互联, 15 Host (共 20 节点)
    """
    def __init__(self, lab_name="simple_bgp"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        routers = [self.lab.add_node(f"r{i}", self.lab.images["quagga"], x=200*i, y=200) for i in range(1, 6)]
        hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=60*i, y=400) for i in range(1, 16)]

        # 2. 创建链路
        # 路由器骨干互联
        for i in range(4):
            self.lab.add_link(routers[i], routers[i+1])
        # 增加冗余链路 (R1-R3, R3-R5) 构成更复杂的 AS 路径
        self.lab.add_link(routers[0], routers[2])
        self.lab.add_link(routers[2], routers[4])

        # 路由器直连主机 (每台 Router 连 3 台 Host)
        for i in range(5):
            for j in range(3):
                self.lab.add_link(routers[i], hosts[i*3 + j])

        # 3. 部署与自动配置
        self.deploy()
        time.sleep(20)

        # 强制开启 IP Forwarding
        for r in [f"r{i}" for i in range(1, 6)]:
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")

        # 4. 调用全局自动配置API
        self.config(senario="bgp")
        time.sleep(10)

if __name__ == "__main__":
    Lab_BGP = BGPRouting()
    
    print("\n--- 🔍 路由表诊断 (R1) ---")
    print(Lab_BGP.lab.execute("r1", "ip route"))

    print("\n--- 正式测试 H1 -> H15 连通性 ---")
    print(Lab_BGP.lab.ping_pair("h1", "h15"))