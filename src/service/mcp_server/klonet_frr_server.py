import os
import re
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 自动向上寻找 .env 文件并加载

from fault_injector.lab_injector_input import SERVICE_INJECT_INPUT
from service.klonet import KlonetFRRAPI  # 替换为你的底层命令执行API

mcp = FastMCP("KlonetFrrServer", log_level="ERROR")

# --- 防火墙与静态路由 (2个) ---
@mcp.tool()
def check_routing_table(router: str, target_ip: str = "") -> str:
    """
    网络不通，怀疑路由器没有去往目标网段的路由，或被引入了黑洞路由.
    ⚠️ 仅限在三层设备 (如 r1, r2, frr路由器) 上使用！
    
    Args:
        router: 待检查的路由器节点名 (如 r1, r2)
        target_ip: 跨网段通信时无法访问的目标 IP 地址

    Returns:
        ans: 路由器底层 FIB 路由表
    """
    lab = os.getenv("LAB_NAME", "")
    API = KlonetFRRAPI(lab)
    
    raw_output = API._run_cmd(router, "ip route show")
    
    if "[ERROR]" in raw_output or "KeyNotExistError" in raw_output:
        return raw_output + "\n[系统警告] 底层执行命令彻底失败，测试环境可能已崩溃，直接提交 unknown_error。"
        
    result = f"【全局路由表 (ip route show)】:\n{raw_output}\n"
    diagnosis_hint = ""
    
    if target_ip:
        clean_ip = target_ip.split('/')[0] 
        get_output = API._run_cmd(router, f"ip route get {clean_ip}")
        result += f"\n【内核路由匹配测试 (ip route get {target_ip})】:\n{get_output}\n"
        
        if "unreachable" in get_output or "Network is unreachable" in get_output:
            # 恢复了场景感知逻辑
            if "bgp" in lab.lower():
                diagnosis_hint += "\n[系统警告] 内核反馈无法找到目标路由。当前为 BGP 环境，路由丢失极可能是 BGP 路由撤销或宣告漏配(bgp_withdraw_route)导致。"
            elif "ospf" in lab.lower() or "rip" in lab.lower():
                diagnosis_hint += "\n[系统警告] 内核反馈无法找到目标路由。当前为 ospf 或 rip 路由环境，请优先排查协议故障。"
            else:
                diagnosis_hint += "\n[系统警告] 内核反馈无法找到目标路由。确诊为静态路由缺失，请检查是否是 route_missing。"
        elif "blackhole" in get_output:
            diagnosis_hint += f"\n[系统警告] 去往 {target_ip} 的流量匹配到了黑洞路由 (blackhole)，请立即调用 submit_diagnosis 提交 static_route_blackhole。"
        else:
            # 恢复了回程路由的强力提示
            diagnosis_hint += (
                f"\n[专家提示] 内核成功匹配到了去往 {target_ip} 的正向路由。\n"
                f"[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。"
            )
    else:
        diagnosis_hint += "\n[专家提示] 未提供 target_ip 参数，请人工核查表项。"
        
    return result + diagnosis_hint

@mcp.tool()
def check_data_plane_drop(router: str) -> str:
    """
    数据面 ACL 阻断（如禁 ICMP）.通过 iptables 检查 FORWARD 链是否存在恶意 DROP 规则.
    ⚠️ 仅限在三层设备 (如 r1, r2, frr路由器) 上使用！

    Args:
        router: 待检查的路由器节点名
    
    Returns:
        ans: iptables FORWARD 链防火墙规则
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetFRRAPI(lab)
    raw_output = API._run_cmd(router, "iptables -L FORWARD -n")

    # 增加底层崩溃拦截
    if "[ERROR]" in raw_output or "KeyNotExistError" in raw_output:
        return raw_output + "\n[系统硬拦截]: 底层执行命令彻底失败，测试环境可能已崩溃，请直接提交 unknown_error。"
        
    # 🕵️‍♂️ 夹带私货：自动诊断逻辑
    diagnosis_hint = ""
    # FORWARD 链通常应该是全 ACCEPT 的，如果出现了 DROP 或 REJECT，说明数据面被阻断了
    if "DROP" in raw_output or "REJECT" in raw_output:
        diagnosis_hint = "\n[系统警告] 发现路由器的 FORWARD 数据面中存在恶意的 DROP 或 REJECT 拦截规则，立即调用 `submit_diagnosis` 提交 router_data_plane_drop。"
    else:
        diagnosis_hint = "\n[专家分析] FORWARD 链全为 ACCEPT，数据平面未阻断流量。"

    return raw_output + diagnosis_hint

# --- BGP 协议 (1个) ---
@mcp.tool()
def check_bgp_status(router: str) -> str:
    """
    使用 BGP 协议的网络出现故障时，一键检查 BGP 邻居状态、配置和路由宣告.

    Args:
        router: 需要检查的路由器名    
    """
    lab = os.getenv("LAB_NAME", "")
    API = KlonetFRRAPI(lab) 
    summary = API._run_cmd(router, "vtysh -c 'show ip bgp summary'")
    config = API._run_cmd(router, "vtysh -c 'show running-config'")
    
    if "[ERROR]" in summary:
        return summary + "\n[系统警告] 环境异常。"

    result = f"【BGP Summary】:\n{summary}\n\n【BGP Config】:\n{config}\n"
    diagnosis_hint = ""
    
    if "neighbor" in config and "shutdown" in config:
        diagnosis_hint = "\n[系统警告] 发现配置中 BGP 邻居被手动关闭 (shutdown)，请调用 submit_diagnosis 提交 bgp_neighbor_shutdown。"
    elif re.search(r'\b(Active|Idle)\b', summary):
        diagnosis_hint = "\n[系统警告] 发现 BGP 邻居状态卡在 Active 或 Idle，未能 Established。极大可能是对端 AS 号配置错误，请调用 submit_diagnosis 提交 bgp_wrong_peer_asn。"
    else:
        # 恢复了防回程路由不通的宣告检查逻辑
        diagnosis_hint = (
            "\n[专家提示] BGP 邻居状态已建联 (Established)。\n"
            "[专家提示] 邻居正常但跨网段 Ping 不通，通常是直连网段未宣告导致回程路由不通。请核对上方 【BGP Config】，若发现 router bgp 下缺少 redistribute connected 或目标网段的 network 宣告，请立即调用 submit_diagnosis 提交 bgp_withdraw_route。"
        )
        
    return result + diagnosis_hint

# --- OSPF 协议 (1个) ---
@mcp.tool()
def check_ospf_status(router: str) -> str:
    """
    使用 OSPF 协议的网络出现故障时，一键检查 OSPF 进程、接口开销(Cost)及被动接口状态

    Args:
        router: 需要检查的路由器名
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetFRRAPI(lab) 
    neighbor = API._run_cmd(router, "vtysh -c 'show ip ospf neighbor'")
    config = API._run_cmd(router, "vtysh -c 'show running-config'")
    
    if "[ERROR]" in neighbor:
        return neighbor + "\n[系统警告] 环境异常。"

    result = f"【OSPF Neighbor】:\n{neighbor}\n\n【OSPF Config】:\n{config}\n"
    diagnosis_hint = ""
    
    # 🌟 修复：增加对 "无输出" 或空字符串的判断，因为守护进程死掉时往往不响应命令
    if "OSPF is not running" in neighbor or "socket" in neighbor.lower() or "无输出" in neighbor or not neighbor.strip():
        diagnosis_hint = "\n[系统警告] 发现 OSPF 进程未运行、无响应或底层 socket 崩溃。确诊：ospf_daemon_crash，请立即调用 submit_diagnosis 提交！"
    elif "passive-interface" in config:
        diagnosis_hint = "\n[系统警告] 发现 OSPF 接口被配置为被动接口 (passive-interface)，导致停止发送 Hello 包，请调用 submit_diagnosis 提交 ospf_passive_interface。"
    elif "ospf cost" in config:
        cost_match = re.search(r'ospf cost (\d+)', config)
        if cost_match and int(cost_match.group(1)) > 100:
            diagnosis_hint = f"\n[系统警告] 发现接口的 OSPF Cost 被异常调高至 {cost_match.group(1)}，导致流量绕路或中断，请调用 submit_diagnosis 提交 ospf_cost_spike。"
        else:
            diagnosis_hint = "\n[专家提示] 发现 ospf cost 配置，请人工核对是否异常。"
    else:
        diagnosis_hint = "\n[专家提示] OSPF 配置未发现明显异常特征。"
        
    return result + diagnosis_hint

# --- RIP 协议 (1个) ---
@mcp.tool()
def check_rip_status(router: str) -> str:
    """
    使用 RIP 协议的网络出现故障时，一键检查 RIP 被动接口、路由过滤和度量值篡改

    Args:
        router: 需要检查的路由器名
    """
    lab = os.getenv("LAB_NAME", "")
    frr_api = KlonetFRRAPI(lab)
    
    status_output = frr_api._run_cmd(router, "vtysh -c 'show ip rip status'")
    config_output = frr_api._run_cmd(router, "vtysh -c 'show running-config'")
    
    diagnosis_hint = ""
    
    # 纯字符串匹配，发现特征直接报警，绝不废话
    if "distribute-list" in config_output:
        diagnosis_hint = "[系统警告] 发现致命异常！配置中存在 `distribute-list` 路由过滤规则，强行屏蔽了所有路由发送！请立即提交 rip_route_filter。"
    elif "offset-list" in config_output:
        diagnosis_hint = "[系统警告] 发现致命异常！配置中存在 `offset-list` 规则，大幅篡改了路由度量值(Metric)导致16跳不可达！请立即提交 rip_metric_offset。"
    elif "passive-interface" in config_output:
        diagnosis_hint = "[系统警告] 发现致命异常！配置中存在 `passive-interface` 语句，导致该接口被动静默！请立即提交 rip_passive_interface。"
    elif "router rip" not in config_output or "无输出" in status_output:
        diagnosis_hint = "[专家提示] 当前节点未配置 RIP。如果是纯转发节点则为正常现象，请继续排查路径上的其他核心节点。"
    else:
        diagnosis_hint = "[专家提示] 该节点 RIP 运行正常，未发现被动接口、过滤或度量值篡改。请继续检查路径上的下一个路由器。"

    return f"【RIP Status】:\n{status_output}\n【RIP Config】:\n{config_output}\n{diagnosis_hint}"

if __name__ == "__main__":
    # 启动 FastMCP 服务，默认基于 stdio(标准输入输出) 与 Agent 通信
    mcp.run(transport="stdio")