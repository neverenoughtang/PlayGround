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
from .tools import get_mcp_tools
from .fault_knowledge import FAULT_REGISTRY

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
    topo_data = api.get_topo_json()
    topo = topo_data["project"]["topo"] if "project" in topo_data and "topo" in topo_data["project"] else topo_data
    
    links_dict = topo.get("links", {})
    all_hosts = api.get_all_hosts()
    all_nodes = api.get_all_nodes()
    controllers = api.get_all_ryu_controllers()
    normal_hosts = [h for h in all_hosts if h not in controllers]

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
    
    # 【优化点 3】：按需检查协议。极大减少调用底层 CLI (vtysh) 的次数
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        def _fetch_node_state(n):
            arp = api._run_cmd(n, "ip neigh")
            iface = api._run_cmd(n, "ip -br link")
            
            bgp, ospf, rip = "", "", ""
            # 根据场景严格剪枝
            if "bgp" in lab_name:
                bgp = api._run_cmd(n, 'vtysh -c "show ip bgp summary" 2>/dev/null')
            elif "ospf" in lab_name:
                ospf = api._run_cmd(n, 'vtysh -c "show ip ospf neighbor" 2>/dev/null')
            elif "rip" in lab_name:
                rip = api._run_cmd(n, 'vtysh -c "show ip rip status" 2>/dev/null')
                
            return n, arp, iface, bgp, ospf, rip

        for n, arp, iface, bgp, ospf, rip in executor.map(_fetch_node_state, all_nodes):
            if arp.strip(): arp_res.append(f"[{n} ARP/Neigh]:\n{arp}")
            if iface.strip(): iface_res.append(f"[{n} Interfaces]:\n{iface}")
            
            # 如果是相关场景且返回了真实数据，才加入报告
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
        f"[FRR]\n{chr(10).join(frr_res) if frr_res else '暂无相关动态路由(FRR)配置'}"
    )

async def global_inspector(state: DiagnoseState):
    """
    【前置全局巡检核心】
    利用 asyncio.to_thread 极速并发下发命令。彻底断绝 Agent 胡乱调用 O(n^2) 耗时工具的可能性。
    """
    print("\n🔍 [Inspector] 正在底座线程池中极速并发采集全网底层健康快照...")
    
    try:
        # 将重度阻塞操作卸载至后台线程，保证 Event Loop 不被卡死
        raw_info = await asyncio.to_thread(_run_heavy_inspections_sync, state['lab_name'])
    except Exception as e:
        print(f"❌ [Inspector] 底层采集崩坏: {e}")
        return {"inspector_result": f"巡检采集异常: {e}"}

    # 使用 Medium 模型进行快速摘要提取，剔除正常冗余信息
    print("🧠 [Inspector] 正在调用 Qwen-Medium 压缩底层日志...")
    llm = load_model(backend_model="qwen3.5-medium")
    prompt = f"网络场景：{state['lab_name']}。请基于以下全网状态快照，总结出明显的异常点(如 ping不通、网卡DOWN、路由邻居卡在Idle等)。只输出纯粹的异常结论。\n\n{raw_info[:8000]}"
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        inspector_summary = f"【全局巡检核心异常报告】\n{res.content}"
    except Exception as e:
        inspector_summary = f"【巡检摘要失败】: {e}"
    
    print("✅ [Inspector] 全局底检任务安全着陆！")
    return {"inspector_result": inspector_summary}

async def supervisor_node(state: DiagnoseState):
    """
    【前置假设拆分】
    根据拓扑和投诉，划分假设域。使用 Medium 模型。
    """
    inspector_result = await global_inspector(state) # 获取全局巡检结果

    print("\n" + "👑 [Supervisor] 正在分析投诉，拆解并行诊断假设域...")
    llm = load_model(backend_model="qwen3.5-medium")
    
    prompt = f"""你是一名专业的网络架构师。

    【当前网络拓扑】
    {state["lab_name"]}

    【可能的故障】
    {FAULT_REGISTRY["common_link"]}
    {FAULT_REGISTRY["common_host"]}
    {FAULT_REGISTRY[state["lab_name"]]}

    【用户投诉】
    {state["problem_info"]}

    【全局巡检结果】
    {inspector_result}

    网络中可能 1 个或者多个故障。请结合网络拓朴、可能的故障、用户投诉、全局巡检结果，提出 2 到 4 个不重叠的【诊断假设】。
    每一个假设必须从【可能的故障】中**挑选出**具体故障名称（不是全部列举）及其详细描述。请直接输出 JSON 格式（必须包含 "hypotheses" 数组）。

    示例: {{
    "hypotheses": [
    "假设A [链路故障] 可能存在以下故障：    
        - link_loss: 发生在 ubuntu 主机上，通过 Linux TC netem 注入丢包规则，表现为网络链路具有一定丢包率（如50%），导致通信不稳定、延迟高或部分数据包丢失
        - link_latency: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟规则，表现为网络延迟异常偏高但抖动极小，导致业务响应缓慢
        - link_jitter: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟抖动规则，表现为网络延迟忽高忽低极不稳定，mdev 数值显著偏高
        - link_bandwidth: 发生在 ubuntu 主机上，通过 Linux TC tbf 令牌桶限速，表现为传输速度被严重限流，网络拥塞严重", 
    "假设B [主机故障] 可能存在以下故障：   
        - ip_misconfig: 发生在 ubuntu 主机上，通过 flush 网卡 IP 后配置错误地址，表现为主机无法与同网段或其他节点正常通信，IP 丢失或配错
        - default_route_missing: 发生在 ubuntu 主机上，通过删除默认路由，表现为主机同网段通信正常但跨网段通信完全不可达
        - arp_poisoning: 发生在 ubuntu 主机上，通过静态绑定伪造 MAC 地址，表现为主机局域网内无法与特定目标通信，ARP 缓存表出现异常条目
        - interface_down: 发生在 ubuntu 主机上，通过 ip link set down 关闭网卡，表现为主机似乎彻底脱网，所有网络连接中断
        - routing_error: 发生在 ubuntu 主机上，通过添加错误的静态路由指向非预期网关，表现为主机无法访问特定外部网段，数据包走向异常
        - mask_error: 发生在 ubuntu 主机上，通过配置错误的子网掩码（如/30），表现为同网段内的部分相邻主机无法直接通信
        - host_port_exhaustion: 发生在 ubuntu 主机上，通过 sysctl 限制可用源端口范围为极窄值，表现为主机应用程序抛出"无法分配请求的地址"错误，无法发起新连接",
    "假设C [DNS故障] 可能存在以下故障：
        - dns_error: 发生在 ubuntu 主机上，通过修改 /etc/resolv.conf 指向错误 DNS 服务器，表现为主机无法访问外部域名网站，域名解析失败",
    "假设D [BGP故障] 可能存在以下故障： 
        - bgp_neighbor_shutdown: 发生在 frr 路由器上，通过 vtysh 配置 neighbor shutdown 管理性关闭 BGP 邻居，表现为某节点跨域通信突然中断，邻居连接失败
        - bgp_withdraw_route: 发生在 frr 路由器上，通过 vtysh 删除 network 宣告或 redistribute connected，表现为邻居正常但某远端网段突然不可达
        - bgp_wrong_peer_asn: 发生在 frr 路由器上，通过 vtysh 配置错误的对端 AS 号，表现为某处 BGP 邻居始终无法建立，状态长期停留在 Idle 或 Active
        - acl_blocking_bgp_traffic: 发生在 frr 路由器上，通过 iptables 阻断 TCP 179 端口，表现为 BGP 会话断开后无法重连
        - bgp_local_pref_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 local-preference 值（如999），表现为跨域流量突然绕行到非预期路径
        - bgp_med_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 MED 值（如9999），表现为对端更偏好其他入口，业务路径切换异常"
        ]
        }}
    """
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        clean_json = res.content.replace("```json", "").replace("```", "").strip()
        hypotheses = json.loads(clean_json).get("hypotheses")
    except:
        hypotheses = ["假设A: 物理链路", "假设B: 协议服务"]
        
    print(f"👑 [Supervisor] 生成假设域：{hypotheses}")
    return {
        "hypotheses": hypotheses,
        "inspector_result": inspector_result
    }


# ==========================================
# 本地测试代码 (仅在直接运行此文件时执行)
# ==========================================
if __name__ == "__main__":
    import asyncio
    import time
    
    # 模拟环境需要加载一下环境变量（确保 .env 和 MCP Server 能正常工作）
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())

    async def test_supervisor_module():
        # 指定要测试的 3 个经典场景
        test_labs = ["sdn_openflow", "p4_star", "simple_bgp"]
        
        for lab in test_labs:
            print(f"\n{'='*80}")
            print(f"🚀 正在测试场景: 【{lab}】")
            print(f"{'='*80}")
            
            # 构造传递给节点的模拟图状态 (DiagnoseState)
            mock_state = {
                "lab_name": lab,
                "netenv_info": f"这是 {lab} 的模拟网络拓扑结构信息（省略具体详情）...",
                "problem_info": "用户投诉：部分主机突然无法跨网段通信，且存在严重的异常丢包和高延迟现象。",
            }
            
            # ---------------------------------------------------------
            # 1. 测试底层同步巡检函数 (获取 Ping/ARP/Interface/FRR 原始数据)
            # ---------------------------------------------------------
            print("\n[阶段 1] ⏳ 正在执行底层原始数据采集 (_run_heavy_inspections_sync) ...")
            start_time = time.time()
            
            try:
                # 放入线程池执行，防止阻塞事件循环
                raw_info = await asyncio.to_thread(_run_heavy_inspections_sync, lab)
                cost_time = time.time() - start_time
                print(f"✅ 原始数据采集完成 (耗时 {cost_time:.2f}s)。")
                print("\n👇 --- 原始巡检数据 (Raw Info) --- 👇")
                # 为了防止输出过长刷屏，只截取前 1500 字展示，你可以根据需要调整
                print(raw_info)
                print("👆 -------------------------------- 👆\n")
            except Exception as e:
                print(f"❌ 原始数据采集失败: {e}")
                continue # 如果连底层获取都失败了，跳过该场景测试

            # ---------------------------------------------------------
            # 2. 测试全局巡检 Agent 节点 (大模型摘要提取)
            # ---------------------------------------------------------
            print("\n[阶段 2] 🧠 正在执行全局巡检 Agent 节点 (global_inspector_node) ...")
            try:
                inspector_res = await global_inspector(mock_state)
                print("\n👇 --- 全局巡检 Agent 提炼结果 --- 👇")
                print(inspector_res.get("inspector_result", "无结果"))
                print("👆 ------------------------------- 👆\n")
                
                # 将巡检结果注入 state，供后续环节或展示参考
                mock_state["inspector_result"] = inspector_res.get("inspector_result", "")
            except Exception as e:
                print(f"❌ 巡检 Agent 分析失败: {e}")

            # ---------------------------------------------------------
            # 3. 测试 Supervisor 假设拆解节点 (任务分发)
            # ---------------------------------------------------------
            print("\n[阶段 3] 👑 正在执行 Supervisor 假设拆解节点 (supervisor_node) ...")
            try:
                supervisor_res = await supervisor_node(mock_state)
                print("\n👇 --- Supervisor 拆解的并行假设域 --- 👇")
                hypotheses = supervisor_res.get("hypotheses", [])
                for idx, hyp in enumerate(hypotheses, 1):
                    print(f"  {idx}. {hyp}")
                print("👆 ----------------------------------- 👆\n")
            except Exception as e:
                print(f"❌ Supervisor 拆解失败: {e}")
            
            print(f"🎉 场景 【{lab}】 模块链路测试完毕！\n")
            time.sleep(2) # 缓冲等待一下，方便终端观察

    # 启动异步测试
    asyncio.run(test_supervisor_module())