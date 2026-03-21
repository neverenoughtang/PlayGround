import os
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 自动向上寻找 .env 文件并加载
import os
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) 

from service.klonet import KlonetBaseAPI  # 请替换为你实际的控制器API类名

mcp = FastMCP("KlonetControllerServer", log_level="ERROR")

@mcp.tool()
def check_sdn_controller(controller: str) -> str:
    """
    检查 SDN 控制器的运行状态. 
    
    Args:
        controller: 控制器节点名称 (如 controller, c0)
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)
    
    # 🌟 终极防兼容性报错版：不用 -E，分两次最简单的 grep，把结果拼起来
    # 为了防止 netstat 没有，同时也查 ss
    port_6653 = API._run_cmd(controller, "netstat -tln | grep 6653 || ss -tln | grep 6653")
    port_6633 = API._run_cmd(controller, "netstat -tln | grep 6633 || ss -tln | grep 6633")
    
    # 额外加一层进程探测（最最原始的 ps，不带 aux，不带中括号防自身）
    process_info = API._run_cmd(controller, "ps | grep ryu-manager | grep -v grep")
    
    # 把所有线索拼在一起
    combined_output = f"{port_6653}\n{port_6633}\n{process_info}".strip()
    
    # 如果拼出来的结果里包含报错信息，直接硬拦截
    if "[ERROR]" in combined_output or "KeyNotExistError" in combined_output:
        return combined_output + "\n[系统警告] 底层执行命令彻底失败，测试环境可能已崩溃，直接提交 unknown_error。"
        
    result = f"【SDN 控制器端口与进程状态】:\n{combined_output}\n"
    
    # 🌟 核心判断：如果上面三条命令全都没有抓到任何带有 6653/6633/ryu 的内容，说明控制器死透了！
    if "6653" not in combined_output and "6633" not in combined_output and "ryu" not in combined_output.lower():
        diagnosis_hint = "\n[系统警告] 🚨 未检测到控制器端口(6653/6633)，也未检测到 ryu 进程！控制器已彻底宕机或崩溃！请立即调用 submit_diagnosis 提交 sdn_controller_crash。"
    else:
        diagnosis_hint = "\n[专家提示] SDN 控制器正在正常运行(端口或进程存活)。如果交换机依然断开连接，说明是交换机配置被恶意篡改（如线断了），请提交 ovs_disconnect_controller！"
        
    return result + diagnosis_hint

if __name__ == "__main__":
    mcp.run()
