import json
from langchain_core.messages import HumanMessage
from utils.llm_models import load_model
from .state import DiagnoseState
from .tools import get_mcp_tools
from .fault_knowledge import FAULT_REGISTRY

async def global_inspector(state: DiagnoseState):
    """
    【前置全局巡检】
    自动执行 MCP 工具获取底层网络健康快照。
    """
    print("\n" + "🔍 [Inspector] 正在并发采集全网底层状态 (Ping/ARP/FRR/Interface)...")
    mcp_tools = await get_mcp_tools(state["lab_name"])
    tool_map = {t.name: t for t in mcp_tools}
    
    try:
        ping_res = await tool_map["get_reachability"].ainvoke({})
        arp_res = await tool_map["check_arp"].ainvoke({"node_names": "all"})
        iface_res = await tool_map["check_interface"].ainvoke({"node_names": "all"})
        frr_res = await tool_map["check_frr"].ainvoke({"node_names": "all"})
    except Exception as e:
        return {"inspector_result": f"巡检系统异常: {e}"}

    raw_info = f"[Ping]\n{ping_res}\n\n[ARP]\n{arp_res}\n\n[Interface]\n{iface_res}\n\n[FRR]\n{frr_res}"
    
    # 使用 Medium 模型进行快速摘要提取，节省后续 Worker 的 Token
    llm = load_model(backend_model="qwen3.5-medium")
    prompt = f"网络场景：{state['lab_name']}。请基于以下全网巡检数据，总结出明显的异常点(例如哪些节点ping不通，网卡DOWN，路由邻居异常等)。只输出异常结论，完全正常的部分忽略。\n{raw_info[:5000]}"
    
    res = await llm.ainvoke([HumanMessage(content=prompt)])
    inspector_summary = f"【全局巡检异常报告】\n{res.content}"
    
    print("🔍 [Inspector] 全局底检完成！")
    return {"inspector_result": inspector_summary}

async def supervisor_node(state: DiagnoseState):
    """
    【前置假设拆分】
    根据拓扑和投诉，划分假设域。使用 Medium 模型。
    """
    inspector_result = await global_inspector() # 获取全局巡检结果

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

    网络中可能 1 个或者多个故障。请结合网络拓朴、可能的故障、用户投诉、全局巡检结果，提出 3 到 6 个不重叠的【诊断假设】。
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