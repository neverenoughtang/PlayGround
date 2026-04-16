from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class StaticRouting(NetworkEnvBase):
    """
    静态路由场景 (规模扩容): 3 Router, 6 Switch, 18 Host (共 27 节点)
    """
    def __init__(self, lab_name="static_routing"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        # 路由器 (三角互联)
        r1 = self.lab.add_node("r1", self.lab.images["new_quagga"], x=300, y=200)
        r2 = self.lab.add_node("r2", self.lab.images["new_quagga"], x=600, y=200)
        r3 = self.lab.add_node("r3", self.lab.images["new_quagga"], x=450, y=100)

        # 交换机 (每台路由器下挂2个交换机，共6个)
        switches = [self.lab.add_node(f"s{i}", self.lab.images["ovs"], x=150*i, y=300) for i in range(1, 7)]
        
        # 主机 (每个交换机下挂3台主机，共18个)
        hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=50*i, y=400) for i in range(1, 19)]

        # 2. 创建链路
        # 路由器互联
        self.lab.add_link(r1, r2, link_name="l_r1_r2")
        self.lab.add_link(r2, r3, link_name="l_r2_r3")
        self.lab.add_link(r3, r1, link_name="l_r3_r1")

        # 路由器 - 交换机
        self.lab.add_link(r1, switches[0]); self.lab.add_link(r1, switches[1])
        self.lab.add_link(r2, switches[2]); self.lab.add_link(r2, switches[3])
        self.lab.add_link(r3, switches[4]); self.lab.add_link(r3, switches[5])

        # 交换机 - 主机
        for i in range(6):
            for j in range(3):
                self.lab.add_link(switches[i], hosts[i*3 + j])

        # 3. 部署与自动配置
        self.deploy()
        time.sleep(20)

        # 4. 调用全局自动配置API
        self.config(senario="static")
        time.sleep(10)

if __name__ == "__main__":
    Lab_Static = StaticRouting()

    print("--- 检查网卡 ---")
    res1 = Lab_Static.lab.execute("h1", "ifconfig")
    print("h1 info:\n", res1)
    
    print("--- 测试连通性 (跨全网) ---")
    print(Lab_Static.lab.ping_pair("h1", "h18"))