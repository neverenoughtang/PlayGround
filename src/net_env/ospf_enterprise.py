from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class OSPFRouting(NetworkEnvBase):
    """
    OSPF分层网络场景: Core(Ring) -> Dist -> Access -> Host
    模拟企业内部大型园区网，通常使用 OSPF 作为 IGP
    """
    def __init__(self, lab_name="ospf_enterprise"):
        super().__init__(lab_name=lab_name)

        # --- 1. 创建节点 ---

        # 1.1 核心层 (Core Layer) - Area 0 骨干区域
        # 使用 Quagga 模拟三层核心路由器
        c1 = self.lab.add_node("c1", self.lab.images["quagga"], x=400, y=300)
        c2 = self.lab.add_node("c2", self.lab.images["quagga"], x=600, y=300)
        c3 = self.lab.add_node("c3", self.lab.images["quagga"], x=500, y=200)

        # 1.2 服务区块 (Service Block)
        # 核心交换机下挂服务器区
        s_sw = self.lab.add_node("ssw", self.lab.images["ovs"], x=500, y=150) 
        dns = self.lab.add_node("dns", self.lab.images["new_ubuntu"], x=420, y=50)
        dhcp = self.lab.add_node("dhcp", self.lab.images["new_ubuntu"], x=500, y=50)
        lb = self.lab.add_node("lb", self.lab.images["new_ubuntu"], x=580, y=50)

        # 1.3 汇聚层 (Distribution Layer) - Area 1
        # 三层设备，负责汇聚接入层流量
        d1 = self.lab.add_node("d1", self.lab.images["quagga"], x=300, y=400)
        d2 = self.lab.add_node("d2", self.lab.images["quagga"], x=700, y=400)

        # 1.4 接入层 (Access Layer)
        # 二层交换机
        a1 = self.lab.add_node("a1", self.lab.images["ovs"], x=300, y=500)
        a2 = self.lab.add_node("a2", self.lab.images["ovs"], x=700, y=500)

        # 终端主机
        h1 = self.lab.add_node("h1", self.lab.images["new_ubuntu"], x=300, y=600)
        h2 = self.lab.add_node("h2", self.lab.images["new_ubuntu"], x=700, y=600)


        # --- 2. 创建链路 ---

        # 2.1 核心层互联 (Ring环网)
        self.lab.add_link(c1, c2)
        self.lab.add_link(c2, c3)
        self.lab.add_link(c3, c1)

        # 2.2 服务区块连接
        self.lab.add_link(c3, s_sw)
        self.lab.add_link(s_sw, dns)
        self.lab.add_link(s_sw, dhcp)
        self.lab.add_link(s_sw, lb)

        # 2.3 核心连接汇聚 (双上联以提高可靠性)
        # D1 同时连接 C1 和 C2
        self.lab.add_link(c1, d1)
        self.lab.add_link(c2, d1)
        # D2 同时连接 C1 和 C2
        self.lab.add_link(c1, d2)
        self.lab.add_link(c2, d2)

        # 2.4 汇聚连接接入
        self.lab.add_link(d1, a1)
        self.lab.add_link(d2, a2)

        # 2.5 接入连接主机
        self.lab.add_link(a1, h1)
        self.lab.add_link(a2, h2)

        # 3. 部署与自动配置
        self.deploy()
        
        time.sleep(20)

        # 4. 调用全局自动配置API
        # OSPF 协议将自动计算全网最短路径
        self.config(senario="ospf")
        
        # 等待收敛 (OSPF 计算路由需要时间)
        time.sleep(15)

if __name__ == "__main__":
    Lab_OSPF = OSPFRouting()
    
    print("--- 开始测试 OSPF 场景连通性 ---")
    
    # 1. 测试跨区域通信: H1 (接入层) -> H2 (接入层)
    # 流量走向: H1 -> A1 -> D1 -> Core -> D2 -> A2 -> H2
    print("测试 H1 -> H2 连通性:")
    print(Lab_OSPF.lab.ping_pair("h1", "h2"))

    # 2. 测试访问服务: H1 -> DNS Server
    print("测试 H1 -> DNS Server 连通性:")
    print(Lab_OSPF.lab.ping_pair("h1", "dns"))