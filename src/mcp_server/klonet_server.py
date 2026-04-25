import asyncio
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

# --- 单独 ping 工具 (1个) ---
# @mcp.tool()
# def ping_by_ip(src_node: str, dst_ip: str) -> str:
#     """
#     从源节点向目标IP发送ICMP Echo Request。

#     Args:
#         src_node: 原节点名
#         dst_ip: 目标 IP 地址
        
#     Returns:
#         response (str): 返回干净的指令输出结果。
#     """
#     lab = os.getenv("LAB_NAME")
#     API = KlonetBaseAPI(lab)    
#     # 优化为 -c 4，加快执行速度
#     return API._run_cmd(src_node, f"ping -c 4 -W 2 {dst_ip}")

@mcp.tool()
def ping_by_name(src_node: str, dst_name: str = "www.baidu.com") -> str:
    """
    应用层 (http) 连通性初筛。仅限于诊断 DNS 故障！

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
    if "ping" in cli_cmd or "ip neigh" == cli_cmd or "ip -br link" == cli_cmd or "show ip bgp summary" in cli_cmd or "show ip ospf neighbor" in cli_cmd or "show ip rip status" in cli_cmd: 
        return "禁止使用此指令！"
    API = KlonetBaseAPI(lab) 
    return API._run_cmd(node, cli_cmd)

@mcp.tool()
async def multi_node_execute(nodes_str: str, command: str) -> str:
    """
    【批处理专属】
    同时在多个节点上并发执行相同的非破坏性查询命令。仅限查询类命令，严禁执行修改类命令。
    Args:
        nodes_str: 逗号分隔的节点名列表，例如 "h1,h2,h3,h4,h5,h6,h7,h8"
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
        final_output.append(f"节点 {n} 执行 {command} 结果: \n{res}")
        
    return "\n".join(final_output)

@mcp.tool()
async def batch_execute(node_cmd: list[tuple[str, str]]) -> str:
    """
    【批处理专属】
    同时在多个节点上并发执行不同的非破坏性查询命令。仅限查询类命令，严禁执行修改类命令。
    
    Args:
        node_cmd: 节点名-指令二元组列表，例如: 
                 [("h1", "ip link show"), ("h2", "ip route"), ("r1", "sysctl net.ipv4.ip_forward")]
    
    Returns:
        str: 各节点执行结果的汇总，按输入顺序展示
    """
    if not node_cmd:
        return "错误：未提供节点-指令列表。"
    
    # 异步并发执行单个任务
    async def execute_task(node: str, cmd: str) -> tuple[str, str]:
        try:
            result = await asyncio.to_thread(node_execute, node, cmd)
            return node, f"✓ {result}"
        except Exception as e:
            return node, f"✗ 执行失败: {str(e)}"
    
    # 并发执行所有任务
    results = await asyncio.gather(*(execute_task(n, c) for n, c in node_cmd))
    
    # 组织输出结果
    final_output = []
    for (node, cmd), (_, result) in zip(node_cmd, results):
        final_output.append(f"节点 {node} 执行 {cmd} 结果: \n{result}")
    
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