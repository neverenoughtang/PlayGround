from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *

from base_netenv import NetworkEnvBase


class StaticRouting(NetworkEnvBase):
    """
    静态路由场景: 2 Router, 4 Switch, 6 Host
    """
    def __init__(self, lab_name="static_routing"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        # 路由器
        r1 = self.lab.add_node("r1", self.lab.images["quagga"], x=300, y=200)
        r2 = self.lab.add_node("r2", self.lab.images["quagga"], x=600, y=200)

        # 交换机 (按照描述：路由器分别连接2个交换机 => 共4个)
        # R1 连接的交换机
        s1 = self.lab.add_node("s1", self.lab.images["ovs"], x=150, y=300)
        s2 = self.lab.add_node("s2", self.lab.images["ovs"], x=300, y=300)
        # R2 连接的交换机
        s3 = self.lab.add_node("s3", self.lab.images["ovs"], x=600, y=300)
        s4 = self.lab.add_node("s4", self.lab.images["ovs"], x=750, y=300)

        # 主机 (第1、2、3、4个交换机分别连接2、1、1、2个主机)
        # S1 -> 2 hosts
        h1 = self.lab.add_node("h1", self.lab.images["ubuntu"], x=50, y=400)
        h2 = self.lab.add_node("h2", self.lab.images["ubuntu"], x=150, y=400)
        
        # S2 -> 1 host
        h3 = self.lab.add_node("h3", self.lab.images["ubuntu"], x=300, y=400)
        
        # S3 -> 1 hosts
        h4 = self.lab.add_node("h4", self.lab.images["ubuntu"], x=600, y=400)

        # S4 -> 2 hosts
        h5 = self.lab.add_node("h5", self.lab.images["ubuntu"], x=700, y=400)
        h6 = self.lab.add_node("h6", self.lab.images["ubuntu"], x=800, y=400)

        # 2. 创建链路 (注意：自动配置不需要指定 IP)
        # R1 - R2
        self.lab.add_link(r1, r2, link_name="l1")

        # R1 - Switches
        self.lab.add_link(r1, s1, link_name="l2")
        self.lab.add_link(r1, s2, link_name="l3")

        # R2 - Switches
        self.lab.add_link(r2, s3, link_name="l4")
        self.lab.add_link(r2, s4, link_name="l5")

        # Switches - Hosts
        self.lab.add_link(s1, h1, link_name="l6")
        self.lab.add_link(s1, h2, link_name="l7")
        
        self.lab.add_link(s2, h3, link_name="l8")
        
        self.lab.add_link(s3, h4, link_name="l9")
        self.lab.add_link(s4, h5, link_name="l10")
        
        self.lab.add_link(s4, h6, link_name="l11")

        # 3. 部署与自动配置
        self.deploy()
        time.sleep(20)

        # 4. 调用全局自动配置API (替代手动 execute ip route)
        self.config(senario="static")
        
        # 等待配置生效
        time.sleep(10)

if __name__ == "__main__":
    Lab_Static = StaticRouting()

    # 这里我们简单测试 h1 的网卡状态
    print("--- 检查网卡 ---")
    res1 = Lab_Static.lab.execute("h1", "ifconfig")
    print("h1 info:\n", res1)
    
    # 尝试 Ping 对端主机
    print("--- 测试连通性 ---")
    print(Lab_Static.lab.ping_pair("h1", "h4"))