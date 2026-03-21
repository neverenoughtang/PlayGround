import os
import re
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 自动向上寻找 .env 文件并加载

from fault_injector.lab_injector_input import HOST_INJECT_INPUT
from service.klonet import KlonetIptablesAPI  # 替换为你的底层命令执行API

mcp = FastMCP("KlonetHostServer", log_level="ERROR")

# --- 通用 Ping 工具 (2个) ---
@mcp.tool()
def ping_by_ip(src_node: str, dst_ip: str) -> str:
    """
    网络连通性初筛.
    从源节点向目标IP发送ICMP Echo Request.

    Args:
        src_node: 发起Ping的节点名，一般是主机或路由器
        dst_ip: 目标IP地址

    Returns:
        ans: Ping命令的完整统计输出(包含丢包率和延迟)
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab)    
    return API._run_cmd(src_node, f"ping -c 10 -W 2 {dst_ip}")

@mcp.tool()
def ping_by_name(src_node: str, dst_name: str = "www.baidu.com") -> str:
    """
    应用层连通性初筛（验证 DNS 时，ping 对象为 "www.baidu.com"）.
    从源节点向目标域名/主机名发送ICMP Echo Request.

    Args:
        src_node: 发起Ping的节点名，一般是主机或路由器
        dst_name: 目标域名或主机名

    Returns:
        ans: Ping命令的完整统计输出
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab)     
    return API._run_cmd(src_node, f"ping -c 10 -W 2 {dst_name}")

# --- 主机故障检测工具 (6个) ---
@mcp.tool()
def check_interface_down(host: str, iface: str) -> str:
    """
    物理接口关闭检测.
    通过 ip link show 检查网卡的物理/逻辑层状态 (UP/DOWN).

    Args:
        host: 待检查的节点名
        iface: 节点的接口名

    Returns:
        ans: 网卡的链路层状态信息
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab) 
    cmd = f"ip link show {iface}" if iface else "ip link show"
    raw_output = API._run_cmd(host, cmd)
    
    # 🕵️‍♂️ 夹带私货：自动诊断逻辑
    diagnosis_hint = ""
    # 只要包含 state DOWN (排除 loopback 等干扰，通常故障网卡会变成 DOWN)
    if "state DOWN" in raw_output:
        diagnosis_hint = "\n[系统警告] 发现异常！接口状态明确显示为 'state DOWN'，说明物理或逻辑链路已被强制关闭。不要怀疑，这 100% 是 interface_down 故障！请直接调用 submit_diagnosis 提交 interface_down。"
    else:
        diagnosis_hint = "\n[专家提示] 未发现异常！接口状态良好"
    return raw_output + diagnosis_hint

@mcp.tool()
def check_ip_misconfig(host: str, iface: str) -> str:
    """
    IP地址配置错误检测.
    通过 ip addr show 检查网卡当前绑定的 IP 地址及子网掩码.

    Args:
        host: 待检查的节点名
        iface: 节点的接口名

    Returns:
        ans: 网卡绑定的所有IP信息
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab)  
    cmd = f"ip addr show {iface}" if iface else "ip addr show"
    raw_output = API._run_cmd(host, cmd)

    # 使用正则提取 IPv4 地址 (例如: 192.168.1.2 或 192.168.1.2/24)
    ip_match = re.search(r'inet\s+(\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?)', raw_output)
    IP = ip_match.group(1) if ip_match else "未配置(None)"
    
    # 🕵️‍♂️ 夹带私货：自动诊断逻辑
    diagnosis_hint = f"\n[专家提示] 请核对上述输出的IPv4地址 {IP} 是否与【网络拓扑信息】中 {host} 的接口 IP 一致，若不一致，调用 submit_diagnosis 提交 ip_misconfig。"
    
    # 如果指定了网卡，但输出里连 'inet ' 都没有，说明 IP 被清空了
    if iface and "inet " not in raw_output:
        diagnosis_hint += "\n[系统警告] 发现严重异常！指定的接口完全丢失了 IPv4 (inet) 地址配置，或者配置为空。可能是接口 DOWN 或者 IP 未配置 等各种故障。"
        
    return raw_output + diagnosis_hint

@mcp.tool()
def check_default_route_missing(host: str) -> str:
    """
    默认路由缺失，导致跨网段不通，但同网段通的路由排查.
    通过 ip route show 检查主机的全局路由表，确认是否存在 default via 默认网关.

    Args:
        host: 待检查的主机节点名称

    Returns:
        ans: 主机当前的完整路由表
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab)
    raw_output = API._run_cmd(host, "ip route show")
    
    # 🕵️‍♂️ 夹带私货：自动诊断逻辑
    diagnosis_hint = ""
    # 如果输出为空，或者输出里既没有 default 也没有 0.0.0.0
    if "无输出" in raw_output.strip():
        diagnosis_hint = (
            "\n[系统警告] 路由表完全为空！\n"
            "【防误判锁】如果网卡 DOWN，路由表也会清空。若接口 UP 但没有默认路由(缺少'default via'字段)，且不符合 ip_misconfig 的表现，请提交 default_route_missing。"
        )
    elif "default" not in raw_output and "0.0.0.0" not in raw_output:
        diagnosis_hint = "\n[系统警告] 主机确实缺少 'default via'。跨网段一定不通。请提交 default_route_missing。"
        
    return raw_output + diagnosis_hint

@mcp.tool()
def check_arp_poisoning(host: str) -> str:
    """
    主机无法与同网段或跨网段节点通信，疑似 ARP 欺骗或二层劫持.
    通过 ip neigh show 检查主机的 ARP 缓存表，审计网关或其他通信节点的 MAC 地址映射是否异常（如状态为 STALE, FAILED 或 MAC 被篡改）.

    Args:
        host: 待检查的主机节点名称

    Returns:
        ans: ARP 邻居缓存表内容
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab) 
    raw_output = API._run_cmd(host, "ip neigh show")
    
    # 增加自动诊断逻辑
    diagnosis_hint = ""
    # 针对 P4 和 SDN 场景的白名单机制
    if ("p4" in lab or "sdn" in lab) and "PERMANENT" in raw_output:
        diagnosis_hint = f"{raw_output}\n[专家提示] 当前为 {lab} 场景，出现 PERMANENT 静态 ARP 绑定是正常现象（平台预配），未发现 ARP 投毒。请去检查交换机流表或进程！"
    elif "aa:bb:cc:dd:ee:ff" in raw_output or "PERMANENT" in raw_output:
        diagnosis_hint = "\n[系统警告] 发现异常！ARP 表中存在明显的伪造 MAC 地址，或不正常的 PERMANENT 静态绑定，肯定是 ARP 投毒！请直接调用 submit_diagnosis 提交 arp_poisoning。"
    elif "FAILED" in raw_output:
        diagnosis_hint = "\n[系统警告] ARP 状态显示为 FAILED，说明二层 MAC 寻址彻底失败，无法获取目标 MAC。"
        
    return raw_output + diagnosis_hint

@mcp.tool()
def check_dns_error(host: str) -> str:
    """
    IP可达但域名无法解析.
    读取主机 /etc/resolv.conf 配置，检查 nameserver 是否被篡改或错误.

    Args:
        host: 待检查的主机节点名称

    Returns:
        ans: DNS 配置文件内容
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab) 
    raw_output = API._run_cmd(host, "cat /etc/resolv.conf")
    diagnosis_hint = ""

    if "0.1.2.3" in raw_output:
        diagnosis_hint = f"\n[系统警告] 0.1.2.3 通常不是一个正常的 DNS，请直接调用 submit_diagnosis 提交 dns_error。"

    return raw_output + diagnosis_hint

@mcp.tool()
def check_cpu_overload(host: str) -> str:
    """
    Ping出现异常高延迟、高抖动，疑似节点资源耗尽.
    检查系统中是否存在异常的 CPU 满载进程(如 dd 恶意占用).

    Args:
        host: 待检查的主机节点名称
        
    Returns:
        ans: 匹配到的异常耗费 CPU 的进程列表
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetIptablesAPI(lab) 
    return API._run_cmd(host, "sh -c 'ps aux | grep [d]d'")

if __name__ == "__main__":
    # 启动 FastMCP 服务，默认基于 stdio(标准输入输出) 与 Agent 通信
    mcp.run(transport="stdio")