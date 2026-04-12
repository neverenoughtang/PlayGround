"""配置文件

可对后端服务器的IP及端口进行配置

"""
import os
from dotenv import load_dotenv
load_dotenv() # 这将加载 .env 文件中的环境变量

#: str: 后端服务器IP
backend_ip = os.getenv("BACKEND_IP")
#: int: 后端服务器端口
backend_port = os.getenv("BACKEND_PORT")
