import os
import re
import socket
import concurrent.futures # ⚠️ 新增导入
from typing import Dict, Optional
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) 

from klonet_base_api import KlonetBaseAPI  

mcp = FastMCP("KlonetServer", log_level="ERROR")

# # --- 全局巡检工具 (4个) ---
# @mcp.tool()
# def get_reachability() -> str:
#     """
#     自动获取全网可达性测试结果（无需输入任何参数）。
#     1. 自动从拓扑中提取所有普通主机进行两两 Ping 测试（并发执行）。
#     2. 自动识别 SDN 控制器，并测试控制器到其【直连】OVS 交换机的连通性。
#     输出结果已通过正则精简，仅保留通断状态、丢包率、错误原因及延迟统计。
#     """
#     lab = os.getenv("LAB_NAME")
#     API = KlonetBaseAPI(lab)
    
#     # 获取底层拓扑以解析链路关系
#     topo_data = API.get_topo_json()
#     if "project" in topo_data and "topo" in topo_data["project"]:
#         topo = topo_data["project"]["topo"]
#     else:
#         topo = topo_data
        
#     links_dict = topo.get("links", {})

#     # 分类网络节点
#     all_hosts = API.get_all_hosts()
#     controllers = API.get_all_ryu_controllers()
#     normal_hosts = [h for h in all_hosts if h not in controllers]

#     def _parse_ping(output: str) -> str:
#         """内部函数：使用正则表达式精简并提取 ping 的核心指标"""
#         loss_match = re.search(r"(\d+)%\s+packet\s+loss", output)
#         loss_rate = loss_match.group(1) + "%" if loss_match else "未知"
        
#         if loss_rate == "0%":
#             status = "✅ 连通"
#         elif loss_rate == "100%":
#             status = "❌ 不通"
#         elif loss_rate != "未知":
#             status = "⚠️ 部分丢包"
#         else:
#             status = "❓ 状态未知"
            
#         error_msg = ""
#         if re.search(r"Destination\s+Net(?:work)?\s+Unreachable", output, re.IGNORECASE):
#             error_msg = " [Destination Network Unreachable]"
#         elif re.search(r"Destination\s+Host\s+Unreachable", output, re.IGNORECASE):
#             error_msg = " [Destination Host Unreachable]"
#         elif "Time to live exceeded" in output:
#             error_msg = " [TTL Exceeded]"
#         elif "Name or service not known" in output or "unknown host" in output.lower():
#             error_msg = " [DNS/Hostname Resolution Failed]"
            
#         rtt_match = re.search(r"(?:rtt|round-trip)\s+min/avg/max/mdev\s+=\s+([0-9\./]+)\s+ms", output)
#         rtt_str = f" | 时延: {rtt_match.group(1)} ms" if rtt_match else ""
        
#         return f"{status} | 丢包率: {loss_rate}{error_msg}{rtt_str}"

#     # ---------------- 核心并发优化区 ----------------
#     def _do_host_ping(src, dst):
#         raw_output = API.ping_pair(src, dst)
#         return f"[{src} -> {dst}] : {_parse_ping(raw_output)}"

#     # 👇 修改 1：接收交换机的 IP 地址并进行 Ping 测
#     # 优化后的控制面 Ping 测函数：支持动态查 IP
#     def _do_ctrl_ping(ctrl, sw_name, sw_ip_from_json):
#         sw_ip = sw_ip_from_json
        
#         # 1. 如果拓扑 JSON 里没有写 IP，主动去交换机容器里现场查！
#         if not sw_ip:
#             # hostname -I 会返回容器的所有 IP，通常第一个就是 Docker 分配的管理网口(eth0) IP
#             raw_ip_output = API._run_cmd(sw_name, "hostname -I")
#             if raw_ip_output and raw_ip_output.strip():
#                 # 取以空格分隔的第一个 IP
#                 sw_ip = raw_ip_output.strip().split()[0]
                
#         # 2. 如果查都查不到，再报未知
#         if not sw_ip:
#             return f"[{ctrl} -> {sw_name}] : ❓ 状态未知 | 未配置且无法动态获取管理IP，无法Ping测"
            
#         # 3. 拿到 IP 后进行真实的 Ping 测
#         raw_output = API._run_cmd(ctrl, f"ping -c 5 -W 2 {sw_ip}")
#         return f"[{ctrl} -> {sw_name}({sw_ip})] : {_parse_ping(raw_output)}"

#     results = []
    
#     # 收集待测试的 Host-to-Host 对
#     host_pairs = [(hi, hj) for hi in normal_hosts for hj in normal_hosts if hi != hj]
    
#     # 👇 修改 2：收集 Controller-to-Switch 时，把 IP 一起解析出来
#     ctrl_pairs = []
#     if controllers:
#         for ctrl in controllers:
#             for link_name, link_info in links_dict.items():
#                 src = link_info.get("source")
#                 tgt = link_info.get("target")
#                 src_type = link_info.get("sourceType", "")
#                 tgt_type = link_info.get("targetType", "")
                
#                 sw_name = None
#                 sw_ip = ""
                
#                 # 判断控制器是否在源或目的端，并且另一端是交换机
#                 if src == ctrl and tgt_type in ["switch", "ovs"]:
#                     sw_name = tgt
#                     # 提取 targetIP，并去掉掩码后缀 (如 /24)
#                     sw_ip = link_info.get("targetIP", "").split("/")[0] 
#                 elif tgt == ctrl and src_type in ["switch", "ovs"]:
#                     sw_name = src
#                     # 提取 sourceIP，并去掉掩码后缀
#                     sw_ip = link_info.get("sourceIP", "").split("/")[0]
                
#                 # 记录 (控制器名, 交换机名, 交换机IP)
#                 if sw_name:
#                     # 使用 set 去重机制防止同一链路被重复添加（针对某些双向记录的拓扑）
#                     if not any(p[1] == sw_name for p in ctrl_pairs):
#                         ctrl_pairs.append((ctrl, sw_name, sw_ip))

#     # 使用多线程池并发执行（限制并发数 20，避免打满底层的 Docker Daemon）
#     with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
#         # 并发执行 Host-to-Host
#         if len(normal_hosts) >= 2:
#             results.append("=== Host-to-Host 可达性 ===")
#             # executor.map 会并发执行并保持返回顺序
#             host_outcomes = executor.map(lambda p: _do_host_ping(p[0], p[1]), host_pairs)
#             results.extend(host_outcomes)
#         else:
#             results.append("[-] 普通主机数量少于 2，跳过 Host-to-Host 测试")
            
#         # 👇 修改 3：并发执行 SDN 控制面测试，传入三个参数
#         if controllers:
#             results.append("\n=== SDN 控制面可达性 (Controller -> Connected OVS) ===")
#             if ctrl_pairs:
#                 ctrl_outcomes = executor.map(lambda p: _do_ctrl_ping(p[0], p[1], p[2]), ctrl_pairs)
#                 results.extend(ctrl_outcomes)
#             else:
#                 results.append("[-] 当前拓扑中控制器没有直连的交换机。")

#     return "\n".join(results)

# @mcp.tool()
# def check_arp(node_names: str = "all") -> str:
#     """
#     检查节点的 ARP/Neigh 表。
#     Args:
#         node_names: 逗号分隔的节点名(如 'h1,h2')，填 'all' 检查所有主机和路由器。
#     """
#     lab = os.getenv("LAB_NAME")
#     API = KlonetBaseAPI(lab)
#     target_nodes = API.get_all_nodes() if node_names == "all" else [n.strip() for n in node_names.split(",")]
    
#     results = []
#     with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
#         def _run(n):
#             out = API._run_cmd(n, "ip neigh")
#             return f"[{n} ARP/Neigh]:\n{out}" if out.strip() else ""
        
#         outcomes = executor.map(_run, target_nodes)
#         results.extend([o for o in outcomes if o])
        
#     return "\n".join(results) if results else "未找到 ARP 记录。"

# @mcp.tool()
# def check_interface(node_names: str = "all") -> str:
#     """
#     检查节点的网卡接口状态 (UP/DOWN)。
#     Args:
#         node_names: 逗号分隔的节点名(如 'h1,r1')，填 'all' 检查所有节点。
#     """
#     lab = os.getenv("LAB_NAME")
#     API = KlonetBaseAPI(lab)
#     target_nodes = API.get_all_nodes() if node_names == "all" else [n.strip() for n in node_names.split(",")]
    
#     results = []
#     with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
#         def _run(n):
#             out = API._run_cmd(n, "ip -br link")
#             return f"[{n} Interfaces]:\n{out}" if out.strip() else ""
            
#         outcomes = executor.map(_run, target_nodes)
#         results.extend([o for o in outcomes if o])
        
#     return "\n".join(results) if results else "获取接口状态失败。"

# @mcp.tool()
# def check_frr(node_names: str = "all") -> str:
#     """
#     检查路由器的 FRR 动态路由状态 (BGP Summary & OSPF Neighbor)。
#     Args:
#         node_names: 逗号分隔的节点名，填 'all' 探测全网。
#     """
#     lab = os.getenv("LAB_NAME")
#     API = KlonetBaseAPI(lab)
#     target_nodes = API.get_all_nodes() if node_names == "all" else [n.strip() for n in node_names.split(",")]
    
#     results = []
#     with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
#         def _run(n):
#             bgp_out = API._run_cmd(n, 'vtysh -c "show ip bgp summary" 2>/dev/null')
#             ospf_out = API._run_cmd(n, 'vtysh -c "show ip ospf neighbor" 2>/dev/null')
#             # 过滤掉不支持 vtysh 的普通主机
#             if "command not found" not in bgp_out and "Exiting" not in bgp_out:
#                 return f"[{n} FRR State]:\n--BGP--\n{bgp_out}\n--OSPF--\n{ospf_out}"
#             return ""
            
#         outcomes = executor.map(_run, target_nodes)
#         results.extend([o for o in outcomes if o])
        
#     return "\n".join(results) if results else "未找到 FRR 配置或路由器节点不支持。"

# --- 单独 ping 工具 (2个) ---
@mcp.tool()
def ping_by_ip(src_node: str, dst_ip: str) -> str:
    """
    从源节点向目标IP发送ICMP Echo Request。

    Args:
        src_node: 原节点名
        dst_ip: 目标 IP 地址
        
    Returns:
        response (str): 返回干净的指令输出结果。
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)    
    # 优化为 -c 4，加快执行速度
    return API._run_cmd(src_node, f"ping -c 4 -W 2 {dst_ip}")

@mcp.tool()
def ping_by_name(src_node: str, dst_name: str = "www.baidu.com") -> str:
    """
    应用层 (http) 连通性初筛。

    Args:
        src_node: 原节点名
        dst_name: 要输入的域名
        
    Returns:
        response (str): 返回干净的指令输出结果。
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)     
    # 优化为 -c 4，加快执行速度
    return API._run_cmd(src_node, f"ping -c 4 -W 2 {dst_name}")

# --- 通用节点执行工具 (2个) ---
@mcp.tool()
def node_execute(node: str, cli_cmd: str) -> str:
    """
    节点容器执行标准指令 (包含 Linux 系统命令与 vtysh FRR 命令)。

    Args:
        node: 节点名称(**除了 bmv2 交换机以外的其他所有节点**)
        cli_cmd: 要输入的指令名称
        
    Returns:
        response (str): 返回干净的指令输出结果。
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab) 
    return API._run_cmd(node, cli_cmd)

# src/agent/diagnose_agent/tools.py
from langchain_core.tools import tool
import asyncio

# klonet 节点执行方法封装成并发批处理
@tool
async def multi_node_execute(nodes_str: str, command: str) -> str:
    """
    【批处理专属】
    同时在多个节点上并发执行相同的非破坏性查询命令。仅限查询类命令，严禁执行修改类命令。
    Args:
        nodes_str: 逗号分隔的节点名列表，例如 "h1,h2,h3,h4"
        command: 要执行的查询命令，例如 "ip link show" 或 "ip route"
    """
    # 分析节点
    node_list = [n.strip() for n in nodes_str.split(",") if n.strip()]
    if not node_list:
        return "错误：未提供节点列表。"
    
    # 异步并发结构
    async def mock_execute(n):
        try:
            result = await asyncio.to_thread(node_execute, n, command)
            return f"[{n}] 执行成功" + result
        except Exception as e:
            return f"[{n}] 执行失败: {str(e)}"
            
    results = await asyncio.gather(*(mock_execute(n) for n in node_list))
    
    final_output = []
    for n, res in zip(node_list, results):
        final_output.append(f"======== {n} ========\n{res}")
        
    return "\n".join(final_output)
    
# --- bmv2 节点执行工具 (4个) --- 
@mcp.tool()
def bmv2_execute(node: str, cli_cmd: str) -> str:
    """
    执行 P4 交换机 (BMv2) 底层 CLI 命令。

    Args:
        node: bmv2 交换机名称
        cli_cmd: 要输入的 CLI 命令
        
    Returns:
        response (str): 返回清洗后的 CLI 输出结果
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)

    full_cmd = f"bash -c 'echo \"{cli_cmd}\" | simple_switch_CLI --thrift-port 9090'"
    raw_output = API._run_cmd(node, full_cmd)

    clean_lines = []
    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Obtaining JSON" in line:
            continue
        if "Control utility for runtime P4 table manipulation" in line:
            continue

        if "RuntimeCmd:" in line:
            content = line.replace("RuntimeCmd:", "").strip()
            if content:
                clean_lines.append(content)
        else:
            clean_lines.append(line)

    return "\n".join(clean_lines)


@mcp.tool()
def bmv2_help(node: str, topic: str = "help") -> str:
    """
    查询 BMv2 CLI 帮助信息，辅助发现 table/action 命令与格式。

    Args:
        node: bmv2 交换机名称
        topic: 帮助主题，例如:
            - help
            - show_tables
            - table_info MyIngress.ipv4_lpm
            - table_show_actions MyIngress.ipv4_lpm

    Returns:
        response (str): 返回 CLI 帮助输出
    """
    return bmv2_execute(node, topic)


@mcp.tool()
def find_p4_ipv4_lpm_table(node: str) -> str:
    """
    自动探测 BMv2 中最可能承载 IPv4 LPM 转发的表名。

    Args:
        node: bmv2 交换机名称

    Returns:
        table_name (str):
            - 成功时返回表名，例如 MyIngress.ipv4_lpm
            - 失败时返回错误提示
    """
    tables_output = bmv2_execute(node, "show_tables")
    if not tables_output:
        return "[Error] 未获取到任何表信息。"

    candidates = []
    for line in tables_output.splitlines():
        line = line.strip()
        if not line:
            continue
        # 优先匹配同时包含 ipv4 和 lpm 的表
        if "ipv4" in line.lower() and "lpm" in line.lower():
            table_name = line.split()[0]
            candidates.append(table_name)

    if candidates:
        return candidates[0]

    return "[Error] 未找到包含 ipv4 和 lpm 关键字的表，请手工检查 show_tables 输出。"


@mcp.tool()
def get_p4_entry_handle_by_ip(switch_name: str, table_name: str, ip_with_prefix: str) -> str:
    """
    解析指定 P4 表中某个 IP 前缀对应的 entry handle。

    Args:
        switch_name: P4 交换机名称
        table_name: 要查询的流表名称，例如 MyIngress.ipv4_lpm
        ip_with_prefix: 目标 IP 地址，建议填写精确前缀，如 10.0.0.1/32

    Returns:
        handle (str):
            - 成功时返回纯数字 handle
            - 失败时返回错误提示
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)

    ip_str = ip_with_prefix.split("/")[0]
    prefix_len = ip_with_prefix.split("/")[1] if "/" in ip_with_prefix else "32"

    try:
        ip_hex = socket.inet_aton(ip_str).hex()
    except Exception as e:
        return f"[Error] IP 地址格式解析失败: {e}"

    dump_res = API._run_cmd(
        switch_name,
        f"bash -c 'echo \"table_dump {table_name}\" | simple_switch_CLI --thrift-port 9090'"
    )

    lines = dump_res.split("\n")
    target_pat = f"{ip_hex}/{prefix_len}"

    # 同时兼容 dump 里可能没有显示 /32 的情况
    for i, line in enumerate(lines):
        low = line.lower().strip()
        if ip_hex in low:
            # 进一步尝试向上找 handle
            for j in range(i, -1, -1):
                if "Dumping entry" in lines[j]:
                    handle_hex = lines[j].split()[-1]
                    try:
                        return str(int(handle_hex, 16))
                    except Exception:
                        return f"[Error] handle 解析失败，原始值: {handle_hex}"

    return f"[Error] 在表 {table_name} 中未找到 IP {ip_with_prefix} 对应的表项。"

# --- OVS 工具(2个) ---
@mcp.tool()
def ovs_list_bridges(node: str) -> str:
    """
    获取 OVS 节点上的 bridge 名称列表。

    Args:
        node: OVS 交换机节点名称

    Returns:
        response (str): 每行一个 bridge 名称
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)
    return API._run_cmd(node, "ovs-vsctl list-br")

@mcp.tool()
def ovs_get_bridge_protocols(node: str, bridge_name: str) -> str:
    """
    获取指定 OVS bridge 的协议版本配置。

    Args:
        node: OVS 交换机节点名称
        bridge_name: 网桥名称

    Returns:
        response (str): 例如 [OpenFlow13] 或 [OpenFlow10]
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)
    return API._run_cmd(node, f"ovs-vsctl get bridge {bridge_name} protocols")


# --- AI 算网场景专属探测工具 (2个) ---
@mcp.tool()
def test_ai_inference(client_node: str, server_ip: str, port: int = 8000) -> str:
    """
    从客户端向 AI 推理节点发起 HTTP 业务探测，获取端到端业务状态与延迟。

    Args:
        client_node: 发起请求的客户端名称
        server_ip: AI 服务端 IP
        port: 服务端口，默认 8000

    Returns:
        response (str): 包含 HTTP 状态码、响应耗时或超时报错
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)

    payload = "{\"prompt\":\"Hello\",\"max_tokens\":10}"
    curl_cmd = (
        f"curl -s -w \"\\nHTTP_CODE:%{{http_code}}\\nTIME_TOTAL:%{{time_total}}s\" "
        f"--max-time 10 -X POST http://{server_ip}:{port}/v1/completions "
        f"-H \"Content-Type: application/json\" "
        f"-d \"{payload}\""
    )

    results = []
    results.append(f"发起推理业务探测: {client_node} -> {server_ip}:{port}")

    raw_res = API._run_cmd(client_node, curl_cmd)

    if "Connection refused" in raw_res:
        results.append("❌ 业务状态: 连接被拒绝 (Connection Refused)")
    elif "Operation timed out" in raw_res or "Timeout" in raw_res:
        results.append("⏳ 业务状态: 请求超时 (Timeout > 10s)")
    else:
        http_code_match = re.search(r"HTTP_CODE:(\d+)", raw_res)
        time_match = re.search(r"TIME_TOTAL:([0-9\.]+)s", raw_res)

        if http_code_match and time_match:
            code = http_code_match.group(1)
            time_s = time_match.group(1)
            if code == "200":
                results.append(f"✅ 业务状态: 正常连通 | HTTP状态码: {code} | 响应耗时: {time_s}s")
            else:
                results.append(f"⚠️ 业务状态: 异常响应 | HTTP状态码: {code} | 响应耗时: {time_s}s")
                results.append(f"原始回包: {raw_res.split('HTTP_CODE')[0].strip()}")
        else:
            results.append(f"❓ 未知响应: {raw_res}")

    return "\n".join(results)

@mcp.tool()
def check_ai_processes(node: str) -> str:
    """
    检查 AI 节点上的 Python 进程与基础进程状态。

    Args:
        node: 节点名称

    Returns:
        response (str): ps aux 的原始结果
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetBaseAPI(lab)
    return API._run_cmd(node, "ps aux")



if __name__ == "__main__":
    mcp.run(transport="stdio")

    # lab_name = os.getenv("LAB_NAME")
    # api = KlonetBaseAPI(lab_name)
    # raw_topo_dict = api.get_topo_json() 
    # print(simplify_topo(lab_name, raw_topo_dict))
    # print(get_reachability())