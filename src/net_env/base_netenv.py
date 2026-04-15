import os
import time
import requests
from dotenv import load_dotenv
load_dotenv() 

from KlonetAPI.klonet import Klonet

"""
注意 Klonet 有以下镜像: ubuntu、new_bmv2、new_ryu、ubuntu_ai、quagga、ovs
"""

class NetworkEnvBase:
    """
    网络实验环境基类，封装了Klonet的基本操作和自动配置API
    """

    def __init__(self, lab_name="default_lab"):
        """
        初始化: 创建实验室
        """
        self.lab_name = lab_name
        self.user_name=os.getenv("USER_NAME")
        self.host_ip=os.getenv("BACKEND_IP")
        self.port=os.getenv("BACKEND_PORT")


        # 登录 Klonet
        self.lab = Klonet()
        self.name = lab_name
        self.lab.klonet_login(
                    project_name=lab_name,  
                    user_name=self.user_name,
                    host_ip=self.host_ip,
                    port=self.port, 
                )
        
        # 确保项目是干净的
        if self.lab.is_topo_deployed:
             print(f"检测到项目 {self.lab_name} 已存在，正在销毁...")
             self.lab.reset_project()
             time.sleep(2)

    def deploy(self):
        """部署拓扑"""
        print(f"正在部署拓扑: {self.lab_name} ...")
        self.lab.deploy()
        time.sleep(5) # 等待部署完成
        print("拓扑部署完成。")

    def config(self, senario: str = "static"):
        """
        [核心API] 全局自动配置IP和路由，默认是静态路由
        """
        try:
            match senario:
                case "static":
                    self.lab.static_config()
                case "bgp":
                    self.lab.bgp_config()                
                case "ospf":
                    self.lab.ospf_config()
                case "rip":
                    self.lab.rip_config()
                case "p4":
                    self.lab.p4_config()
                case "sdn":
                    self.lab.sdn_config()
        except Exception as e:
            print(f"❌ 请求 {senario} 自动配置API时发生异常: {e}")

    def undeploy(self):
        """销毁拓扑"""
        print(f"正在销毁拓扑: {self.lab_name} ...")
        self.lab.reset_project()
        print("销毁完成。")

if __name__ == "__main__":
    LAB = NetworkEnvBase()
    print(LAB.lab.images)