import os
import re
import json
import asyncio
import itertools
import concurrent.futures
from langchain_core.messages import HumanMessage

from utils.llm_models import load_model
from mcp_server.klonet_base_api import KlonetBaseAPI
from .state import DiagnoseState


def _parse_ping(output: str) -> str:
    """内部函数：使用正则表达式精简并提取 ping 的核心指标"""
    loss_match = re.search(r"(\d+)%\s+packet\s+loss", output)
    loss_rate = loss_match.group(1) + "%" if loss_match else "未知"
    
    if loss_rate == "0%":
        status = "✅ 连通"
    elif loss_rate == "100%":
        status = "❌ 不通"
    elif loss_rate != "未知":
        status = "⚠️ 部分丢包"
    else:
        status = "❓ 状态未知"
        
    error_msg = ""
    if re.search(r"Destination\s+Net(?:work)?\s+Unreachable", output, re.IGNORECASE):
        error_msg = " [Destination Network Unreachable]"
    elif re.search(r"Destination\s+Host\s+Unreachable", output, re.IGNORECASE):
        error_msg = " [Destination Host Unreachable]"
    elif "Time to live exceeded" in output:
        error_msg = " [TTL Exceeded]"
    elif "Name or service not known" in output or "unknown host" in output.lower():
        error_msg = " [DNS/Hostname Resolution Failed]"
        
    rtt_match = re.search(r"(?:rtt|round-trip)\s+min/avg/max/mdev\s+=\s+([0-9\./]+)\s+ms", output)
    rtt_str = f" | 时延: {rtt_match.group(1)} ms" if rtt_match else ""
    
    return f"{status} | 丢包率: {loss_rate}{error_msg}{rtt_str}"

def _run_heavy_inspections_sync(lab_name: str) -> str:
    """
    【同步封装块 - 极致性能优化版】
    1. 引入 itertools.combinations 消除无向对重复测试。
    2. 根据 lab_name 按需下发 FRR 指令，杜绝无脑全量捞取。
    3. 调大 I/O 线程池 max_workers 容量。
    """
    api = KlonetBaseAPI(lab_name)

    all_hosts = api.get_all_hosts()
    all_routers = api.get_all_routers()
    all_switches = api.get_all_ovs()
    controllers = api.get_all_ryu_controllers()
    normal_hosts = [h for h in all_hosts if h not in controllers]
    all_nodes = all_hosts + all_routers + all_switches

    ping_results = []
    
    # 【优化点 1】：利用 combinations 替代双重 for 循环。
    # 从 排列 (Permutations) 降维成 组合 (Combinations)。20 个节点从 380 次直接降至 190 次！
    host_pairs = list(itertools.combinations(normal_hosts, 2))

    def _do_host_ping(pair):
        src, dst = pair
        raw_output = api.ping_pair(src, dst)
        return f"[{src} -> {dst}] : {_parse_ping(raw_output)}"

    # 【优化点 2】：Ping 测是纯粹的网络 I/O 等待，不吃 CPU。
    # 操作系统处理这类挂起的线程游刃有余，放宽到 50 并发甚至 100 都可以。
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        if len(normal_hosts) >= 2:
            ping_results.append("=== Host-to-Host 可达性 ===")
            ping_results.extend(list(executor.map(_do_host_ping, host_pairs)))

    # --- 2. 收集控制器 -> 交换机 连通性 (保持不变，略) ---
    ctrl_pairs = []
    # ... (省略收集 ctrl_pairs 的代码) ...
    def _do_ctrl_ping(pair):
        ctrl, sw_name, sw_ip = pair
        if not sw_ip:
            raw_ip = api._run_cmd(sw_name, "hostname -I")
            sw_ip = raw_ip.strip().split()[0] if raw_ip and raw_ip.strip() else ""
        if not sw_ip: return f"[{ctrl} -> {sw_name}] : ❓ 未配置管理IP"
        raw_output = api._run_cmd(ctrl, f"ping -c 4 -W 2 {sw_ip}")
        return f"[{ctrl} -> {sw_name}({sw_ip})] : {_parse_ping(raw_output)}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        if ctrl_pairs:
            ping_results.append("\n=== SDN 控制面可达性 ===")
            ping_results.extend(list(executor.map(_do_ctrl_ping, ctrl_pairs)))

    # --- 3. 收集全网节点状态 (ARP/Interface/FRR) ---
    arp_res, iface_res, frr_res = [], [], []
    
    # 确保之前已经定义了 all_nodes = all_hosts + all_routers + all_switches
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        def _fetch_node_state(n):
            arp, iface, bgp, ospf, rip = "", "", "", "", ""
            
            # 🛡️ 剪枝 1: 只有 Host 和 Router 查 ARP (OVS 查不出内容，徒增耗时)
            if n in all_hosts or n in all_routers:
                arp = api._run_cmd(n, "ip neigh")
            
            # 🛡️ 剪枝 2: 严格过滤冗余接口，只保留拓扑连通线 (to 开头)
            raw_iface = api._run_cmd(n, "ip -br link")
            if raw_iface:
                # 过滤出以 'to' 开头的行，丢弃 'lo', 'eth0', 'ovs-system', 'tunl0' 等
                iface_lines = [line for line in raw_iface.splitlines() if line.strip().startswith("to")]
                iface = "\n".join(iface_lines)
            
            # 🛡️ 剪枝 3: 只有 FRR 路由器才执行动态路由命令
            if n in all_routers:
                if "bgp" in lab_name:
                    bgp = api._run_cmd(n, 'vtysh -c "show ip bgp summary" 2>/dev/null')
                elif "ospf" in lab_name:
                    ospf = api._run_cmd(n, 'vtysh -c "show ip ospf neighbor" 2>/dev/null')
                elif "rip" in lab_name:
                    rip = api._run_cmd(n, 'vtysh -c "show ip rip status" 2>/dev/null')
                    
            return n, arp, iface, bgp, ospf, rip

        # 🚀 【注意】这里必须用 all_nodes 映射，保证全网的 "to" 接口都能被收集到！
        for n, arp, iface, bgp, ospf, rip in executor.map(_fetch_node_state, all_nodes):
            if arp and arp.strip(): 
                arp_res.append(f"[{n} ARP/Neigh]:\n{arp}")
                
            if iface and iface.strip(): 
                iface_res.append(f"[{n} Interfaces]:\n{iface}")
            
            # 只有相关场景且返回了真实数据，才加入报告
            frr_content = []
            if bgp and "command not found" not in bgp and "Exiting" not in bgp:
                frr_content.append(f"--BGP--\n{bgp}")
            if ospf and "command not found" not in ospf and "Exiting" not in ospf:
                frr_content.append(f"--OSPF--\n{ospf}")
            if rip and "command not found" not in rip and "Exiting" not in rip:
                frr_content.append(f"--RIP--\n{rip}")
                
            if frr_content:
                frr_res.append(f"[{n} FRR State]:\n" + "\n".join(frr_content))

    return (
        f"[Ping]\n{chr(10).join(ping_results)}\n\n"
        f"[ARP]\n{chr(10).join(arp_res) if arp_res else '未找到 ARP 记录'}\n\n"
        f"[Interface]\n{chr(10).join(iface_res) if iface_res else '获取接口状态失败'}\n\n"
        f"[FRR]\n{chr(10).join(frr_res) if frr_res else '暂无相关动态路由(FRR)配置'}\n"
    )

async def global_inspector(state: DiagnoseState):
    """
    【前置全局巡检核心】
    利用 asyncio.to_thread 极速并发下发命令。彻底断绝 Agent 胡乱调用 O(n^2) 耗时工具的可能性。
    """
    print("\n🔍 [Inspector] 正在底座线程池中极速并发采集全网底层健康快照...")
    inspector_summary = ""

    try:
        # 将重度阻塞操作卸载至后台线程，保证 Event Loop 不被卡死
        raw_info = await asyncio.to_thread(_run_heavy_inspections_sync, state['lab_name'])
        inspector_summary += raw_info
    except Exception as e:
        print(f"❌ [Inspector] 底层采集崩坏: {e}")
        return {"inspector_result": f"巡检采集异常: {e}"}

    # 使用 Small 模型进行快速摘要提取，剔除正常冗余信息
    print("🧠 [Inspector] 正在调用 Qwen-Small 压缩底层日志...")
    llm = load_model(backend_model="qwen3.5-small")
    prompt = f"网络场景：{state['lab_name']}。请基于以下全网状态快照，**全面**总结出明显的异常点(如 ping不通、网卡DOWN、路由邻居卡在Idle等)。只输出纯粹的异常结论。\n\n{raw_info}"
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        inspector_summary += f"【全局巡检报告】\n{res.content}"
    except Exception as e:
        inspector_summary += f"【巡检摘要失败】: {e}"
    
    print("✅ [Inspector] 全局底检任务着陆！")
    print(raw_info)
    print(inspector_summary)

    return {"inspector_result": inspector_summary}