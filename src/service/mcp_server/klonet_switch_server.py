import os
import re
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) 

from service.klonet import KlonetBaseAPI, KlonetBMv2API  # 请替换为你实际的交换机API类名

mcp = FastMCP("KlonetSwitchServer", log_level="ERROR")

# --- OVS 交换机 (合并为1个) ---
@mcp.tool()
def check_ovs_status(switch: str) -> str:
    """
    检查 Open vSwitch (OVS) 的运行状态、SDN 控制器连接以及流表信息.
    
    Args:
        switch: OVS 交换机节点名称 (如 s1, s2)
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)
    
    # 获取控制器连接状态
    vsctl_output = API._run_cmd(switch, "ovs-vsctl show")
    
    if "[ERROR]" in vsctl_output or "KeyNotExistError" in vsctl_output:
        return vsctl_output + "\n[系统警告] 底层执行命令彻底失败，测试环境可能已崩溃，直接提交 unknown_error。"

    # 🌟 修复：动态获取网桥名称，而不是写死节点名
    br_output = API._run_cmd(switch, "ovs-vsctl list-br")
    bridge_name = br_output.strip().split('\n')[0] if br_output.strip() else switch
        
    # 获取底层流表
    ofctl_output = API._run_cmd(switch, f"ovs-ofctl dump-flows {bridge_name}") 
        
    result = f"【OVS 状态 (ovs-vsctl show)】:\n{vsctl_output}\n\n【OVS 流表 (ovs-ofctl dump-flows {bridge_name})】:\n{ofctl_output}\n"
    diagnosis_hint = ""
    
    if "is_connected: true" not in vsctl_output:
        diagnosis_hint += (
            "\n[系统警告] 未在 OVS 状态中检测到 is_connected: true，交换机与 SDN 控制器已断开连接！\n"
            "【防误判锁】这可能是交换机配置断开(ovs_disconnect_controller)，也可能是控制器本身死机了(sdn_controller_crash)。\n"
            "务必先调用 `check_sdn_controller` 工具检查控制器进程。如果进程死了，提交 sdn_controller_crash；如果进程活着，说明只是连接断了，提交 ovs_disconnect_controller！"
        )
    elif "actions=drop" in ofctl_output.lower():
        diagnosis_hint += "\n[系统警告] 在 OVS 流表中发现了明确的 actions=drop 丢弃动作，导致流量被阻断！请立即调用 submit_diagnosis 提交 ovs_global_drop_flow。"
    else:
        diagnosis_hint += "\n[专家提示] OVS 控制器已连接，且流表中未发现 drop 规则，数据平面基础正常。"
        
    return result + diagnosis_hint

# --- BMv2 (P4) 交换机 (合并为1个) ---
@mcp.tool()
def check_bmv2_status(switch: str) -> str:
    """
    检查 P4 BMv2 交换机的进程存活状态和底层流表动作.
    
    Args:
        switch: P4 交换机节点名称 (如 s1, s2)
    """
    lab = os.getenv("LAB_NAME", "")
    API = KlonetBMv2API(lab)
    
    # 彻底抛弃 ps 命令！直接使用官方封装去拉取流表 (内含正确的 --thrift-port 9090)
    flow_output = API._exec_cli_cmd(switch, "table_dump MyIngress.ipv4_lpm")
    
    diagnosis_hint = ""
    
    # 逻辑 1: 进程崩溃 (排在第一位，因为死了拿不到流表)
    # 如果 CLI 连不上 Thrift 端口，说明进程死透了
    if "Could not connect" in flow_output or "Connection refused" in flow_output:
        ps_status = "【严重异常】未检测到 P4 交换机响应！"
        diagnosis_hint = "[系统警告] 无法连接到 BMv2 CLI！BMv2 交换机进程已彻底崩溃 (或 Thrift 端口断开)，数据平面瘫痪！请立即提交 bmv2_process_crash。"
        
    # 逻辑 2: 流表级丢弃 (排在第二位)
    elif "drop" in flow_output.lower():
        ps_status = "进程存活，CLI 响应正常"
        diagnosis_hint = "[系统警告] 在 P4 流表中发现了针对目标 IP 的 drop (丢弃) 动作！数据包被强行阻断。请立即提交 p4_table_drop。"
        
    # 逻辑 3: 错误转发 (排在最后兜底)
    else:
        ps_status = "进程存活，CLI 响应正常"
        diagnosis_hint = "[专家提示] BMv2 进程存活，且流表中未发现 drop 动作。若 Ping 依然 100% 丢包，说明出端口(egress_port)或 MAC 映射到了错误的接口！确诊为 p4_wrong_forwarding。"
        
    return f"【BMv2 进程状态】:\n{ps_status}\n\n【BMv2 流表信息】:\n{flow_output}\n\n{diagnosis_hint}"

if __name__ == "__main__":
    mcp.run()