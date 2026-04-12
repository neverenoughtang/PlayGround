from dotenv import load_dotenv
load_dotenv() 
import time
import requests

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class BGPRouting(NetworkEnvBase):
    """
    BGP网络场景: 3 Router 线性连接 (模拟不同AS或跨域), 直连 Host, 无 Switch
    拓扑结构:
    [H1] -- [R1] -- [R2] -- [R3] -- [H4]
                      |
                   [H2, H3]
    """
    def __init__(self, lab_name="simple_bgp"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        # 路由器 (核心转发节点)
        r1 = self.lab.add_node("r1", self.lab.images["quagga"], x=200, y=200)
        r2 = self.lab.add_node("r2", self.lab.images["quagga"], x=500, y=200)
        r3 = self.lab.add_node("r3", self.lab.images["quagga"], x=800, y=200)

        # 主机 (终端节点)
        # R1 连接 1 个主机
        h1 = self.lab.add_node("h1", self.lab.images["new_ubuntu"], x=200, y=400)
        
        # R2 连接 2 个主机
        h2 = self.lab.add_node("h2", self.lab.images["new_ubuntu"], x=450, y=400)
        h3 = self.lab.add_node("h3", self.lab.images["new_ubuntu"], x=550, y=400)
        
        # R3 连接 1 个主机
        h4 = self.lab.add_node("h4", self.lab.images["new_ubuntu"], x=800, y=400)

        # 2. 创建链路
        # 路由器互联 (骨干链路)
        self.lab.add_link(r1, r2, link_name="link_r1_r2")
        self.lab.add_link(r2, r3, link_name="link_r2_r3")

        # 路由器直连主机 (接入链路)
        self.lab.add_link(r1, h1)
        
        self.lab.add_link(r2, h2)
        self.lab.add_link(r2, h3)
        
        self.lab.add_link(r3, h4)

        # 3. 部署与自动配置
        self.deploy()
        
        # === 关键修复 1: 等待 Quagga 守护进程完全启动 ===
        # 防止 zebra 启动后清空 API 下发的静态路由
        time.sleep(20)

        # === 关键修复 2: 强制开启 IP Forwarding ===
        # 确保 Linux 内核允许转发包，防止 Quagga 配置未生效
        routers = ["r1", "r2", "r3"]
        for r in routers:
            self.lab.execute(r, "sysctl -w net.ipv4.ip_forward=1")

        # 4. 调用全局自动配置API
        self.config(senario="bgp")
        
        # 等待配置生效
        time.sleep(10)

if __name__ == "__main__":
    Lab_BGP = BGPRouting()
    
    print("\n--- 🔍 路由表诊断 (R1) ---")
    # 打印 R1 的路由表，确认去往 192.168.5.0 (H4网段) 的路由是否存在
    route_info = Lab_BGP.lab.execute("r1", "ip route")
    print(route_info)

    # --- 开始正式测试 ---
    print("\n--- 正式测试 H1 -> H4 连通性 ---")
    ping_res = Lab_BGP.lab.ping_pair("h1", "h4")
    print(ping_res)