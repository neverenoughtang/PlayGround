import os
import time
import requests
from dotenv import load_dotenv
load_dotenv() 

from KlonetAPI.klonet import Klonet

"""
注意 Klonet 有以下镜像: 
'new_ryu', 'new_bmv2', 'quagga', 'ovs', 'ubuntu', 'snort', 'udt', 'pantheon', 'CP', 'host_hardware', 'vit-base-patch16-224', 
'ubuntu1804_py38_torchcpu', 'yolov8n-obb', 'vit-large-patch32-384', 'google-vit-base-v3', 'google-vit-large-v3', 
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

    # def auto_configure(self):
    #     """
    #     [核心API] 全局自动配置IP和路由，默认是 OSPF 协议
    #     """

    #     try:
    #         # 发送 PUT 请求触发自动配置
    #         url = (
    #         "http://" + self.host_ip + ":" + self.port
    #         + "/topo/autoconfiguration/?user=" + self.user_name 
    #         + "&project_name=" + self.lab_name
    #         )
    #         payload = ""
    #         headers = {
    #             "User-Agent": "muti-agent",
    #             "Content-Type": "application/json",
    #             "Accept": "*/*",
    #             "Host": self.host_ip + ":" + self.port,
    #             "Connection": "keep-alive",
    #         }
    #         response = requests.request("PUT", url=url, headers=headers, data=payload)

    #         if response.status_code == 200:
    #             print("✅ 全局自动配置成功！")
    #             print(f"响应内容: {response.text}")
    #         else:
    #             print(f"❌ 自动配置失败，状态码: {response.status_code}")
    #             print(f"错误信息: {response.text}")
    #     except Exception as e:
    #         print(f"❌ 请求自动配置API时发生异常: {e}")


    def undeploy(self):
        """销毁拓扑"""
        print(f"正在销毁拓扑: {self.lab_name} ...")
        self.lab.reset_project()
        print("销毁完成。")