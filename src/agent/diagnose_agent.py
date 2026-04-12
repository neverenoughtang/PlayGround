import os
import sys
import time
import json
import asyncio
from typing import TypedDict, Annotated, Sequence, Literal
from operator import add
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langchain_mcp_adapters.client import MultiServerMCPClient

# ==========================================
# 故障类型注册表 (按场景分类)
# ==========================================
FAULT_REGISTRY = {
    "common_link": """1. 链路层故障（适用于所有网络场景）: 
    - link_loss: 发生在 ubuntu 主机上，通过 Linux TC netem 注入丢包规则，表现为网络链路具有一定丢包率（如50%），导致通信不稳定、延迟高或部分数据包丢失
    - link_latency: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟规则，表现为网络延迟异常偏高但抖动极小，导致业务响应缓慢
    - link_jitter: 发生在 ubuntu 主机上，通过 Linux TC netem 注入延迟抖动规则，表现为网络延迟忽高忽低极不稳定，mdev 数值显著偏高
    - link_bandwidth: 发生在 ubuntu 主机上，通过 Linux TC tbf 令牌桶限速，表现为传输速度被严重限流，网络拥塞严重""",

    "common_host": """2. 主机层故障（适用于所有网络场景）: 
    - ip_misconfig: 发生在 ubuntu 主机上，通过 flush 网卡 IP 后配置错误地址，表现为主机无法与同网段或其他节点正常通信，IP 丢失或配错
    - default_route_missing: 发生在 ubuntu 主机上，通过删除默认路由，表现为主机同网段通信正常但跨网段通信完全不可达
    - arp_poisoning: 发生在 ubuntu 主机上，通过静态绑定伪造 MAC 地址，表现为主机局域网内无法与特定目标通信，ARP 缓存表出现异常条目
    - interface_down: 发生在 ubuntu 主机上，通过 ip link set down 关闭网卡，表现为主机似乎彻底脱网，所有网络连接中断
    - dns_error: 发生在 ubuntu 主机上，通过修改 /etc/resolv.conf 指向错误 DNS 服务器，表现为主机无法访问外部域名网站，域名解析失败
    - cpu_overload: 发生在 ubuntu 主机上，通过 stress-ng 打满 CPU 资源，表现为主机系统严重卡顿，业务处理缓慢，CPU 空闲率趋近于0
    - routing_error: 发生在 ubuntu 主机上，通过添加错误的静态路由指向非预期网关，表现为主机无法访问特定外部网段，数据包走向异常
    - mask_error: 发生在 ubuntu 主机上，通过配置错误的子网掩码（如/30），表现为同网段内的部分相邻主机无法直接通信
    - host_port_exhaustion: 发生在 ubuntu 主机上，通过 sysctl 限制可用源端口范围为极窄值，表现为主机应用程序抛出"无法分配请求的地址"错误，无法发起新连接""",

    "static_routing": """3. FRR 路由器故障（当前场景特有）: 
    - route_missing: 发生在 frr 路由器上，通过 ip route del 删除目标网段路由，表现为主机发往特定网段的跨网段流量完全不通，提示网络不可达
    - static_route_blackhole: 发生在 frr 路由器上，通过 ip route replace blackhole 将目标网段路由改为黑洞，表现为某业务网段的数据包被神秘丢弃，流量有去无回
    - data_plane_drop: 发生在 frr 路由器上，通过 iptables FORWARD 链阻断 ICMP 报文，表现为 Ping 测试全部超时但其他 TCP/UDP 连接可能正常
    - frr_service_down: 发生在 frr 路由器上，通过 pkill zebra/bgpd 杀掉 FRR 守护进程，表现为路由器突然停止一切动态路由转发能力，导致局部网络瘫痪
    - ip_forward_disabled: 发生在 frr 路由器上，通过 sysctl 关闭 IPv4 转发开关，表现为路由器本机可达但转发经过它的业务流量全部中断
    - router_interface_ip_wrong: 发生在 frr 路由器上，通过 flush 接口 IP 后配置错误地址，表现为与该路由器直连的网段全部异常，ARP 与网关解析出现问题""",

    "simple_bgp": """4. BGP 路由器故障（当前场景特有）: 
    - bgp_neighbor_shutdown: 发生在 frr 路由器上，通过 vtysh 配置 neighbor shutdown 管理性关闭 BGP 邻居，表现为某节点跨域通信突然中断，邻居连接失败
    - bgp_withdraw_route: 发生在 frr 路由器上，通过 vtysh 删除 network 宣告或 redistribute connected，表现为邻居正常但某远端网段突然不可达
    - bgp_wrong_peer_asn: 发生在 frr 路由器上，通过 vtysh 配置错误的对端 AS 号，表现为某处 BGP 邻居始终无法建立，状态长期停留在 Idle 或 Active
    - acl_blocking_bgp_traffic: 发生在 frr 路由器上，通过 iptables 阻断 TCP 179 端口，表现为 BGP 会话断开后无法重连
    - bgp_local_pref_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 local-preference 值（如999），表现为跨域流量突然绕行到非预期路径
    - bgp_med_spike: 发生在 frr 路由器上，通过 vtysh route-map 设置异常高的 MED 值（如9999），表现为对端更偏好其他入口，业务路径切换异常""",

    "ospf_enterprise": """5. OSPF 路由器故障（当前场景特有）: 
    - ospf_passive_interface: 发生在 frr 路由器上，通过 vtysh 配置 passive-interface 使接口停止发送 Hello 报文，表现为某处原本正常的 OSPF 邻居突然断开
    - ospf_cost_spike: 发生在 frr 路由器上，通过 vtysh 设置接口 OSPF cost 为异常高值（如65000），表现为流量发生大规模路径切换
    - ospf_daemon_crash: 发生在 frr 路由器上，通过 pkill ospfd 杀掉 OSPF 守护进程，表现为某路由器完全丢失所有 OSPF 路由
    - acl_blocking_ospf_traffic: 发生在 frr 路由器上，通过 iptables 阻断 IP 协议号89（OSPF），表现为链路物理畅通但 OSPF 邻居持续超时消失
    - ospf_neighbor_misconfig: 发生在 frr 路由器上，通过 vtysh 设置不一致的 Hello 定时器，表现为 OSPF 邻接关系始终无法建立
    - ospf_area_misconfig: 发生在 frr 路由器上，通过 vtysh 将接口网段宣告到错误区域，表现为某些区域间路由传播异常，部分 OSPF 邻居无法正常建立
    - ospf_auth_misconfig: 发生在 frr 路由器上，通过 vtysh 单侧配置 OSPF 认证或配置不一致密钥，表现为链路本身可达但某条 OSPF 邻接关系突然无法维持""",

    "rip_internet": """6. RIP 路由器故障（当前场景特有）: 
    - rip_passive_interface: 发生在 frr 路由器上，通过 vtysh 配置 passive-interface 使接口停止发送 RIP 更新，表现为邻居无法再收到本端发送的 RIP 更新
    - rip_route_filter: 发生在 frr 路由器上，通过 vtysh 配置 distribute-list 阻断路由发布，表现为特定网段的对端学不到该路由
    - rip_metric_offset: 发生在 frr 路由器上，通过 vtysh offset-list 增加 RIP 度量值至15或更高，表现为特定 RIP 路由完全无法跨越多跳传播（度量值达16视为不可达）
    - acl_blocking_rip_traffic: 发生在 frr 路由器上，通过 iptables 阻断 UDP 520 端口，表现为邻居长时间学不到任何新路由宣告
    - rip_version_mismatch: 发生在 frr 路由器上，通过 vtysh 强制修改 RIP 版本（v1/v2 不兼容），表现为部分网段路由神秘丢失或聚合错误，BadPackets 计数增加
    - rip_timer_misconfig: 发生在 frr 路由器上，通过 vtysh timers basic 设置异常大的定时器值（如999秒），表现为路由收敛需要数十分钟甚至无法收敛
    - rip_network_withdraw: 发生在 frr 路由器上，通过 vtysh 删除 network 宣告，表现为原本可达的远端网段突然消失""",

    "p4_star": """7. P4 交换机故障（当前场景特有）: 
    - p4_bmv2_process_crash: 发生在 bmv2 交换机上，通过 pkill simple_switch 杀掉 BMv2 运行时进程，表现为途经 P4 交换机的数据流彻底中断
    - p4_table_drop: 发生在 bmv2 交换机上，通过修改 P4 转发表项动作为 drop，表现为某主机通往某 IP 丢包严重
    - p4_wrong_forwarding: 发生在 bmv2 交换机上，通过修改 P4 转发表项参数为错误 MAC 或端口号，表现为发往某个特定 IP 的数据包始终无法到达
    - p4_table_entry_missing: 发生在 bmv2 交换机上，通过删除 P4 转发表项，表现为原本互通的两台主机忽然彻底无法通信
    - p4_default_action_drop: 发生在 bmv2 交换机上，通过修改 P4 表默认动作为 drop，表现为新出现或未显式配置的流量全部无法通过交换机""",

    "sdn_openflow": """8. SDN 交换机/控制器故障（当前场景特有）: 
    - sdn_controller_crash: 发生在 ryu 控制器上，通过 pkill ryu-manager/python 杀掉控制器进程，表现为 SDN 网络失去控制，新上的主机无法通信
    - ovs_disconnect: 发生在 ovs 交换机上，通过 ovs-vsctl del-controller 删除控制器配置，表现为某台交换机不再接受控制器管理
    - ovs_global_drop: 发生在 ovs 交换机上，通过 ovs-ofctl 注入高优先级全局 DROP 流表，表现为途经某台交换机的所有流量都被无差别丢弃
    - southbound_wrong_controller: 发生在 ovs 交换机上，通过 ovs-vsctl set-controller 配置错误的控制器地址，表现为交换机仍在运行但始终无法与控制器建立控制连接
    - southbound_protocol_mismatch: 发生在 ovs 交换机上，通过 ovs-vsctl 设置不兼容的 OpenFlow 协议版本，表现为控制器提示报文格式无法识别，下属 OVS 失去动态控制能力
    - flow_rule_shadowing: 发生在 ovs 交换机上，通过 ovs-ofctl 注入高优先级通配规则覆盖控制器策略，表现为业务流量不再按控制器预期路径转发，网络策略似乎整体失效
    - flow_rule_loop: 发生在 ovs 交换机上，通过 ovs-ofctl 注入自回环流表规则（in_port=X, output:X），表现为网络出现流量死循环，带宽被迅速挤占
    - ovs_fail_secure: 发生在 ovs 交换机上，通过 ovs-vsctl set-fail-mode secure 关闭本地兜底转发，表现为控制器短暂异常后交换机不再进行本地兜底转发""",

    "ai_inference": """9. AI 推理服务故障（当前场景特有）:
    - ai_service_crash: 发生在 ubuntu 主机上，通过 pkill python3 杀掉 AI 推理服务进程，表现为 AI 助手突然不再回复任何消息
    - compute_cpu_starvation: 发生在 ubuntu 主机上，通过 stress-ng 打满 CPU 资源，表现为 AI 吐字极度缓慢
    - compute_memory_exhaustion: 发生在 ubuntu 主机上，通过 stress-ng 占用大量内存（如95%），表现为 AI 服务突然无响应，推理服务频繁超时
    - inference_port_blocked: 发生在 ubuntu 主机或 frr 路由器上，通过 iptables 阻断推理服务端口（如8000），表现为能 Ping 通服务器但推理 API 全部超时
    - tcp_rst_injection: 发生在 frr 路由器上，通过 iptables FORWARD 链注入 TCP RST 报文，表现为连接建立后很快被异常重置
    - cross_layer_traffic_blackhole: 发生在 frr 路由器上，通过 iptables FORWARD 链选择性丢弃特定目的端口流量，表现为跨机房请求算力节点时业务大包被神秘丢弃"""
}

# ==========================================
# 路径配置
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
if src_dir not in sys.path: 
    sys.path.insert(0, src_dir)

from utils.llm_models import load_model
from utils.diagnose_experience_sql import DiagnoseExperienceBase
from utils.fault_diagnose_rag import FaultDiagnosisKnowledgeBase

# ==========================================
# 1. 状态定义
# ==========================================
class DiagnoseState(TypedDict):
    # 输入参数
    lab_name: str
    netenv_info: str
    problem_info: str
    backend_model: str
    max_steps: int     # 召回步数限制（包含工具调用/思考次数+工具输出次数）
    time_limit: float  # 新增时间限制（秒）
    expected_fault: str # 期望的故障归因
    expected_location: str # 期望的故障位置节点
    
    # 中间状态
    global_ping_summary: str      # 全局巡检总结
    fault_symptom: str            # 简略故障表现
    knowledge_context: str        # 经验知识（固定 + 成功）
    messages: Annotated[Sequence[BaseMessage], add]  # LLM 对话记录
    
    # 输出结果
    fault_location: str
    diagnosis_result: str
    location_correct: bool      # 【新增】故障位置是否正确
    attribution_correct: bool   # 【新增】故障归因是否正确
    tool_call_count: int
    execution_time: float
    token_usage: dict
    
    # 内部计时
    start_time: float  # 诊断开始时间戳

# ==========================================
# 2. 核心函数工具定义
# ==========================================
@tool
def submit_diagnosis(fault_location: str, root_cause: str) -> str:
    """
    当且仅当确认故障诊断完成时调用。必须且只能调用一次。
    
    Args:
        fault_location: 故障发生的节点位置，只能从【当前网络场景】中选择节点名填入
        root_cause: 故障原因，只能从【故障类型说明】包含的 58 种故障之中选择小写字母+下划线的字符串填入
    
    Returns:
        确认信息（包含 [DIAGNOSIS_COMPLETED] 标记）
    """
    return f"[DIAGNOSIS_COMPLETED] fault_location: {fault_location}; root_cause: {root_cause}"


# 全局缓存 MCP 工具和 Client，避免每次执行图都重启进程
_MCP_TOOLS_CACHE = None
_MCP_CLIENT = None

async def get_mcp_tools(lab_name: str):
    """
    获取 MCP 工具集（含全局缓存优化）
    
    功能：
    1. 首次调用时启动 MCP Server 并缓存工具列表
    2. 后续调用直接返回缓存，避免重复启动进程
    3. 将 submit_diagnosis 工具与 MCP Server 工具合并
    
    Returns:
        工具列表（包含 submit_diagnosis + klonet_server 提供的所有工具）
    """
    global _MCP_TOOLS_CACHE, _MCP_CLIENT
    
    if _MCP_TOOLS_CACHE is not None:
        return _MCP_TOOLS_CACHE
    
    print("🔧 [MCP] 正在启动 MCP Server 并加载工具集...")
    
    mcp_server_dir = os.path.join(src_dir, "mcp_server")
    custom_env = os.environ.copy()
    custom_env["LAB_NAME"] = lab_name
    
    # 强制剔除控制台提示符环境变量
    custom_env.pop("PS1", None)
    custom_env.pop("PROMPT_COMMAND", None)

    connections = {}
    server_path = os.path.join(mcp_server_dir, "klonet_server.py")
    
    if os.path.exists(server_path):
        connections["klonet_server"] = {
            "command": sys.executable, 
            "args": [server_path],
            "transport": "stdio", 
            "env": custom_env
        }
    else:
        print(f"❌ [MCP] 未找到 MCP Server: {server_path}")
        return [submit_diagnosis]
    
    _MCP_CLIENT = MultiServerMCPClient(connections)
    server_tools = await _MCP_CLIENT.get_tools()
    
    # 合并自定义工具和 MCP 工具
    _MCP_TOOLS_CACHE = [submit_diagnosis] + server_tools
    
    print(f"✅ [MCP] 成功加载 {len(_MCP_TOOLS_CACHE)} 个工具（含 1 个自定义 + {len(server_tools)} 个 MCP 工具）")
    
    return _MCP_TOOLS_CACHE

async def cleanup_mcp_client():
    """
    清理 MCP Client 资源（在诊断流程结束后调用）
    """
    global _MCP_CLIENT, _MCP_TOOLS_CACHE
    
    if _MCP_CLIENT is not None:
        try:
            # 新版本通常通过关闭底层的 transport 来清理，
            # 如果 adapter 没有暴露 close，直接置空即可，或调用其内部 session 的清理
            print("✅ [MCP] 正在释放 MCP 资源引用...")
        except Exception as e:
            print(f"⚠️ [MCP] 清理时发生错误: {e}")
        finally:
            _MCP_CLIENT = None
            _MCP_TOOLS_CACHE = None


# ==========================================
# 3. 智能体节点 (Nodes)
# ==========================================
async def global_inspector_node(state: DiagnoseState):
    """
    【全局巡检智能体】
    
    功能：
    1. 调用 get_reachability() 工具获取全局 ping 信息
    2. 用 LLM 摘要出 ping 不通的内容
    3. 输出简略故障表现（"ping不通"/"全网联通"/"延迟高"/"暂无表现"）
    
    输出：
    - global_ping_summary: 总结后的 ping 信息
    - fault_symptom: 简略故障表现
    """
    print("\n" + "="*60)
    print("👁️ [Global Inspector] 正在执行全局可达性巡检...")
    print("="*60)

    # 1. 获取工具并调用 get_reachability
    tools = await get_mcp_tools(state["lab_name"])
    reachability_tool = next((t for t in tools if t.name == "get_reachability"), None)
    
    if not reachability_tool:
        print("❌ [Global Inspector] 未找到 get_reachability 工具！")
        return {
            "global_ping_summary": "【系统错误】: 未找到全局巡检工具",
            "fault_symptom": "暂无表现"
        }
    
    # 调用工具获取原始 ping 数据
    raw_ping_data = await reachability_tool.ainvoke({})
    print(f"📊 [Global Inspector] 原始 ping 数据长度: {len(str(raw_ping_data))} 字符")
    
    # 2. 用 LLM 摘要 ping 数据
    llm = load_model(backend_model=state["backend_model"])
    
    summary_prompt = f"""你是网络诊断专家。请分析以下全局 ping 结果，提取信息：
【当前网络信息】
{state["netenv_info"]}

【原始 Ping 数据】
{raw_ping_data}

【任务】
判断故障表现类型，从以下选项中选择一个：
   - "全网联通"：所有节点都能互相 ping 通
   - "ping不通"：存在节点间完全无法通信，100% 丢包   
   - "延迟高"：能 ping 通，但延迟异常偏高（如 500 ms）
   - "抖动"：能 ping 通，但抖动严重（如一会 1000 ms，一会 10 ms）
   - "丢包"：能 ping 通，但有一定丢包率（如丢包率 60%）

【输出格式】
第一行：故障表现类型（只写上述选项之一）
第二行：ping 不通/延迟高/抖动/丢包的详细信息（写清楚哪些节点不能 ping 通哪些节点、延迟高、抖动严重或丢包；若全网联通则写"ICMP 能通，但可能存在其他问题"）
第三行：结合整个拓扑的疑似故障的节点（若全网联通则写"所有节点都可能存在其他网络问题"）

示例输出 1 ：
    [结论] ping不通
    [详情] 节点 h1 无法 ping 通 h3、h4。
    [嫌疑] 疑似 r1 路由器或主机 h1 出现故障。

示例输出 2：
    [结论] 延迟高
    [详情] 节点 h1 无法 ping 任何节点延迟都是 500 ms。
    [嫌疑] 疑似 r1 路由器或主机 h1 出现故障。    
"""
    
    summary_response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
    summary_text = summary_response.content.strip()
    
    # 3. 解析输出
    lines = summary_text.split("\n")[0] # 第一行
    fault_symptom = lines[5:].strip() if lines else "暂无表现"
    
    print(f"\n[Global Inspector] 巡检完成 ✅")
    print(f"   - Ping 总结: {summary_text}...")
    
    return {
        "global_ping_summary": summary_text,
        "fault_symptom": fault_symptom
    }


async def experience_planner_node(state: DiagnoseState):
    """
    【经验规划智能体】
    
    功能：
    1. 从 MySQL 提取成功经验（基于场景 + 故障表现）
    2. 从 Milvus 提取固定经验（基于场景 + 用户投诉）
    3. 拼接两部分经验成统一字符串
    
    输出：
    - knowledge_context: 拼接好的经验字符串
    """
    print("\n" + "="*60)
    print("📚 [Experience Planner] 正在提取诊断经验...")
    print("="*60)
    
    # 1. 从 MySQL 提取成功经验
    print("🔍 [MySQL] 正在检索历史成功经验...")
    mysql_db = DiagnoseExperienceBase()
    
    # 构建查询关键词：用户投诉 + 故障表现
    search_keyword = f"{state['problem_info']} {state['fault_symptom']}"
    
    mysql_experience = await mysql_db.search(
        lab_name=state["lab_name"],
        keyword=search_keyword,
        limit=5  # 最多返回 10 条不重复根因的经验
    )
    
    # 2. 从 Milvus 提取固定经验
    print("🔍 [Milvus] 正在检索固定诊断手册...")
    milvus_kb = FaultDiagnosisKnowledgeBase(force_rebuild=False)
    
    milvus_experience = milvus_kb.search(
        query=state["problem_info"],
        current_scenario=state["lab_name"],
        stage1_k=20,
        stage2_k=10,
        final_k=5,
        enable_adaptive=True
    )
    
    # 3. 拼接经验
    def truncate_text(text, max_len=2000):
            return text[:max_len] + "..." if len(text) > max_len else text

    clean_mysql = truncate_text(mysql_experience, 2000)
    clean_milvus = truncate_text(milvus_experience, 2000)

    knowledge_context = f"""
    【历史成功经验 (精简)】:
    {clean_mysql}

    【固定诊断手册 (精简)】:
    {clean_milvus}
    """
    
    print(f"[Experience Planner] 经验提取完成 ✅")
    print(f"   - MySQL 经验长度: {len(clean_mysql)} 字符")
    print(f"   - Milvus 经验长度: {len(clean_milvus)} 字符")
    
    return {"knowledge_context": knowledge_context}


async def diagnosis_expert_node(state: DiagnoseState):
    """
    【深度诊断专家智能体】
    
    功能：
    1. 基于系统提示词（包含网络信息、用户投诉、巡检结果、经验知识）
    2. 生成推理（Thought）和工具调用（Action）
    3. 记录 Token 消耗
    
    输出：
    - messages: 追加 AI 消息（可能包含工具调用）
    - token_usage: 更新 Token 统计
    """
    print("\n" + "="*60)
    print("🧠 [Diagnosis Expert] 正在进行深度推理...")
    print("="*60)
    
    # 1. 检查是否超时或超步数
    current_time = time.time()
    elapsed_time = current_time - state["start_time"]
    
    if elapsed_time > state["time_limit"]:
        print(f"⏰ [Diagnosis Expert] 诊断超时！已用时 {elapsed_time:.2f}秒，超过限制 {state['time_limit']}秒")
        return {
            "messages": [AIMessage(content="[TIMEOUT] 诊断超时，强制终止")]
        }
    
    if state["tool_call_count"] >= state["max_steps"]:
        print(f"🚫 [Diagnosis Expert] 已达最大步数限制 {state['max_steps']} 步")
        return {
            "messages": [AIMessage(content="[MAX_STEPS] 达到最大步数限制，强制终止")]
        }

    # 2. 核心修复点：将新建的 HumanMessage 保存到待返回列表中
    current_messages = list(state["messages"])
    new_messages_to_return = []  # 用于收集本轮产生的新消息，存入全局 State
    
    if not current_messages:
        guide_msg = (f"请结合提示词中的经验开始排查，优先调用工具定位故障。")
        human_msg = HumanMessage(content=guide_msg)
        current_messages.append(human_msg)
        new_messages_to_return.append(human_msg) # 必须加入返回列表，否则下轮会丢失！

    # 3. 加载工具和模型
    llm = load_model(backend_model=state["backend_model"])
    tools = await get_mcp_tools(state["lab_name"])
    llm_with_tools = llm.bind_tools(tools)
    
    # 拼装系统提示词
    fault_info = FAULT_REGISTRY["common_host"] + FAULT_REGISTRY["common_link"] + FAULT_REGISTRY[state["lab_name"]]
    sys_prompt = f"""你是一名网络排障专家，负责诊断网络故障。

【当前网络场景】
{state["netenv_info"]}

【用户投诉】
{state["problem_info"]}

【全局巡检结果】
{state["global_ping_summary"]}

【排障经验知识】
{state["knowledge_context"]}

【故障优先级】
链路层故障 (Link) > 路由协议层 (BGP/OSPF/RIP/FRR) > 数据平面 (P4/SDN) > 主机层 (Host) > 应用层 (AI)

【故障说明】
{fault_info}

【网络参数说明】
- host_name/node: 节点名（如 'h1', 'server'）
- link: 链路名（如 'l1', 'l8'），注意不是网卡名
- iface: 网卡接口名（如 'tor1_1', 'tos1_1'），以 'to' 开头
- command: 包含参数的完整命令（如 'ping -c 5 192.168.1.22'）

【平台指令规范】⚠️
- **绝对禁止**
1. 输出重定向符: `>` `>>`
   错误: `echo "config" > /etc/file.conf`
   正确: 不要在命令行中写文件
2. 逻辑拼接符: `&&` `||`
   错误: `pkill zebra && pkill bgpd`
   正确: 分两次调用 `node_execute`
3. 管道符: `|`
   错误: `ps aux | grep zebra`
   正确: 执行 `ps aux` 后用 Python 或 LLM 自己提取
4. 命令替换: `` `command` `` 或 `$(command)`
   错误: `kill -9 $(pidof zebra)`
   正确: 直接用 `pkill zebra`
5. 单引号陷阱（复杂传参时）
   错误: `vtysh -c 'router bgp 65000'`
   正确: `vtysh -c "router bgp 65000"`
- 化繁为简: 一个动作需要 3 步，必须调用 3 次工具
- 所见即所得: 不要在命令行中做逻辑判断（if/for 循环）
- 只读不写: 尽量避免动态向容器内写入脚本

【诊断任务】
1. 结合网络场景、用户投诉、全局巡检结果和排障经验
2. 依据规范调用工具，逐步缩小故障范围
3. 确诊故障节点位置和故障根因后，**必须调用** `submit_diagnosis` 工具提交答案
4. 你有 {state["max_steps"]} 次尝试机会，剩余步数: {state["max_steps"] - state["tool_call_count"]}
5. 时间限制: {state["time_limit"]}秒，已用时: {elapsed_time:.2f}秒

【工作流规范】
1. 仔细分析全局巡检结果，锁定嫌疑节点范围
2. 根据故障表现（ping不通/延迟高/全网联通）选择诊断方向
3. 按照 **拓扑类型 → 嫌疑节点类型 → 可能根因** 的顺序分层排查
4. 优先使用非破坏性观察类命令（show/dump/tc qdisc show/ip addr/vtysh show 等）
5. 确诊后**立即调用** `submit_diagnosis` 工具提交答案（故障位置和故障原因）

【注意事项】
- 切勿一次性调用大量不相关工具，应按逻辑链条逐步推进
- 同样的工具+参数不要调用两次以上
- 🚨 请保持推理过程简洁，不要重复生成已知的背景信息。如果已经有嫌疑范围，请立即调用工具进行验证。
- ⚠ 保持语言简洁！
"""
    
    # 4. 组合最终传给大模型的消息列表
    messages_for_llm = [SystemMessage(content=sys_prompt)] + current_messages
    
    # 5. 调用 LLM 生成响应，并增加 Timeout 控制
    try:
        response = await asyncio.wait_for(llm_with_tools.ainvoke(messages_for_llm), timeout=240.0)
    except asyncio.TimeoutError:
        print("⚠️ [Diagnosis Expert] LLM API 请求超时！")
        return {"messages": [AIMessage(content="[ERROR] LLM API 响应超时")]}
    except Exception as e:
        print(f"❌ [Diagnosis Expert] LLM 调用抛出异常: {e}")
        raise e
    
    # 将 LLM 的输出也放入待返回列表
    new_messages_to_return.append(response)
    
    # 6. 统计 Token 消耗
    usage = state["token_usage"].copy()
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        usage["input_tokens"] += response.usage_metadata.get("input_tokens", 0)
        usage["output_tokens"] += response.usage_metadata.get("output_tokens", 0)
        usage["total_tokens"] += response.usage_metadata.get("total_tokens", 0)
    
    # 7. 打印推理内容
    if hasattr(response, 'content') and response.content:
        print(f"\n💭 [Thought]: {response.content[:200]}...")
    
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"🔧 [Action]: 准备调用 {len(response.tool_calls)} 个工具")
    
    # 8. 确保第一轮创建的 HumanMessage 和模型回复的 AIMessage 一并存入 State
    return {
        "messages": new_messages_to_return,
        "token_usage": usage
    }


async def tool_filter_node(state: DiagnoseState):
    """
    【工具执行与过滤智能体】
    
    功能：
    1. 执行上一步 LLM 生成的工具调用
    2. 拦截 submit_diagnosis 工具，提取诊断结果
    3. 对超长输出（> 1000 字符）进行智能截断
    4. 更新工具调用计数
    
    输出：
    - messages: 追加 ToolMessage（工具执行结果）
    - tool_call_count: 更新工具调用计数
    - diagnosis_result: 若调用了 submit_diagnosis，提取根因
    - fault_location: 若调用了 submit_diagnosis，提取故障位置
    """
    last_msg = state["messages"][-1]
    
    # 检查是否有工具调用
    if not (hasattr(last_msg, 'tool_calls') and last_msg.tool_calls):
        return {}
    
    print("\n" + "="*60)
    print("🛠️ [Tool Filter] 正在执行工具调用...")
    print("="*60)
    
    tools = await get_mcp_tools(state["lab_name"])
    tool_map = {t.name: t for t in tools}
    
    results = []
    tool_count = state["tool_call_count"]
    diagnosis_res = state.get("diagnosis_result", "")
    fault_loc = state.get("fault_location", "")
    location_correct = False      # 【新增】默认为 False
    attribution_correct = False   # 【新增】默认为 False

    for tc in last_msg.tool_calls:
        tool_count += 1
        tool_name = tc["name"]
        tool_args = tc["args"]
        
        print(f"\n🔧 [Tool {tool_count}] {tool_name}")
        print(f"   参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")
        
        # 执行工具
        t_func = tool_map.get(tool_name)
        if not t_func:
            print(f"❌ [Tool Filter] 未找到工具: {tool_name}")
            results.append(ToolMessage(
                tool_call_id=tc["id"],
                name=tool_name,
                content=f"[ERROR] 未找到工具: {tool_name}"
            ))
            continue
        
        try:
            raw_output = await t_func.ainvoke(tool_args)
        except Exception as e:
            print(f"❌ [Tool Filter] 工具执行失败: {e}")
            results.append(ToolMessage(
                tool_call_id=tc["id"],
                name=tool_name,
                content=f"[ERROR] 工具执行失败: {str(e)}"
            ))
            continue
        
        # 拦截 submit_diagnosis
        if tool_name == "submit_diagnosis":
            diagnosis_res = tool_args.get("root_cause", "unknown")
            fault_loc = tool_args.get("fault_location", "unknown")
            print(f"\n✅ [诊断完成] 故障位置: {fault_loc}, 根因: {diagnosis_res}")

            # 【新增】立即计算正确性
            location_correct = (fault_loc.strip().lower() == 
                              state.get("expected_location", "").strip().lower())
            attribution_correct = (diagnosis_res.strip().lower() == 
                                  state.get("expected_fault", "").strip().lower())
            
        raw_str = str(raw_output)
        print(f"   输出长度: {len(raw_str)} 字符")
        
        # 智能截断超长输出
        if len(raw_str) > 1000:
            print(f"   ⚠️ 输出超长，触发智能截断...")
            raw_str = raw_str[:998]

        llm = load_model(backend_model=state["backend_model"])  
        
        clean_prompt = f"""你是一名专业的网络工程师，请提取关键信息（不超过 200 字符）。

【当前网络场景】
{state["netenv_info"]}

【用户投诉】
{state["problem_info"]}

【全局巡检结果】
{state["global_ping_summary"]}

【调用工具】
[工具] {tool_name} | [参数] {tool_args}

【工具输出】
{raw_str}

【任务】
结合网络拓朴、用户投诉和全局巡检结果，提取异常信息(错误的 netem 规则、IP、掩码、默认路由、路由表 DROP 规则、邻居 shutdown 状态等)，忽略冗余日志。

示例一：
    【当前网络场景】
     simple_bgp 的拓扑信息:

    [节点列表]
    - h1 [host] | 接口: tor1_1(192.168.2.2/24) | 默认网关: 192.168.2.1
    - h2 [host] | 接口: tor2_1(192.168.3.2/24) | 默认网关: 192.168.3.1
    - h3 [host] | 接口: tor2_1(192.168.4.2/24) | 默认网关: 192.168.4.1
    - h4 [host] | 接口: tor3_1(192.168.5.2/24) | 默认网关: 192.168.5.1
    - r1 [router] | 接口: tor2_1(192.168.0.1/24), toh1_1(192.168.2.1/24)
    - r2 [router] | 接口: tor1_1(192.168.0.2/24), toh2_1(192.168.3.1/24), toh3_1(192.168.4.1/24), tor3_1(192.168.1.1/24)
    - r3 [router] | 接口: toh4_1(192.168.5.1/24), tor2_1(192.168.1.2/24)

    [链路]
    - 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
    - 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
    - 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
    - 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
    - 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
    - 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

    【用户投诉】
    主机 h1 ping 不通 h3。

    【全局巡检结果】
    [结论] ping不通
    [详情] 节点 h1 无法 ping 通任何节点。
    [嫌疑] 疑似 r1 路由器或主机 h1 出现故障。

    【调用工具】
    [工具] check_bgp_status | [参数] 'router': 'r1'

    【工具输出】
    BGP router identifier 192.168.2.1, local AS number 65001
    RIB entries 3, using 336 bytes of memory
    Peers 1, using 9088 bytes of memory

    Neighbor        V         AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
    192.168.0.2     4 65002      11      12        0    0    0 00:00:53 Idle (Admin)

    Total number of neighbors 1

    Total num. Established sessions 0
    Total num. of routes received     0

    【BGP Config】:
    Building configuration...

    Current configuration:
    !
    hostname Router
    log stdout
    !
    password zebra
    enable password zebra
    !
    interface eth0
    !
    interface lo
    !
    interface toh1_1
    !
    interface tor2_1
    !
    interface tunl0
    !
    router bgp 65001
    bgp router-id 192.168.2.1
    network 192.168.0.0/24
    network 192.168.2.0/24
    redistribute connected
    timers bgp 5 15
    neighbor 192.168.0.2 remote-as 65002
    neighbor 192.168.0.2 shutdown
    neighbor 192.168.0.2 next-hop-self
    !
    address-family ipv6
    exit-address-family
    exit
    !
    ip forwarding
    !
    line vty
    !
    end

你应该输出：
    r1 与邻居 192.168.0.2（r2）的 BGP 会话状态是 "Idle (Admin)"，表示被管理员手动关闭了，BGP 配置中明确有 `neighbor 192.168.0.2 shutdown` 命令，导致 BGP 邻居关系无法建立。

"""
        
        summary = await llm.ainvoke([HumanMessage(content=clean_prompt)])
        final_output = f"【工具输出】\n{raw_str}\n [专家发现] {summary.content}"
        
        print(f"   ✅ 执行成功，返回内容: {final_output}...")
        
        results.append(ToolMessage(
            tool_call_id=tc["id"],
            name=tool_name,
            content=final_output
        ))
    
    return {
        "messages": results,
        "tool_call_count": tool_count,
        "diagnosis_result": diagnosis_res,
        "fault_location": fault_loc,
        "location_correct": location_correct,      # 【新增】
        "attribution_correct": attribution_correct  # 【新增】
    }


async def summary_node(state: DiagnoseState):
    """
    【总结智能体】
    
    功能：
    1. 检查诊断是否成功（故障位置正确 + 故障原因正确）
    2. 若成功，调用 LLM 从完整诊断轨迹中提炼关键步骤
    3. 通过结构化输出将经验写入 MySQL 数据库
    
    输出：
    - 无（直接操作数据库）
    """
    print("\n" + "="*60)
    print("📝 [Summary] 正在检查诊断结果...")
    print("="*60)
    
    # 1. 判断诊断是否成功
    # 成功条件：故障位置正确 AND 故障原因正确
    location_correct = state.get("location_correct", False)
    attribution_correct = state.get("attribution_correct", False)
    is_success = location_correct and attribution_correct
    
    print(f"   期望故障位置: {state.get('expected_location', 'N/A')}")
    print(f"   实际故障位置: {state.get('fault_location', 'N/A')}")
    print(f"   位置判断: {'✅ 正确' if location_correct else '❌ 错误'}")
    print()
    print(f"   期望故障原因: {state.get('expected_fault', 'N/A')}")
    print(f"   实际故障原因: {state.get('diagnosis_result', 'N/A')}")
    print(f"   原因判断: {'✅ 正确' if attribution_correct else '❌ 错误'}")
    print()
    print(f"   最终结果: {'🎉 诊断成功' if is_success else '⚠️ 诊断失败'}")
    
    if not is_success:
        print("\n" + "="*60)
        print("⚠️ [Summary] 诊断未成功，跳过经验总结")
        print("="*60)
        return {}
    
    print("\n" + "="*60)
    print("📝 [Summary] 诊断成功！正在提炼关键步骤并写入数据库...")
    print("="*60)
    
    # 2. 构建完整诊断轨迹（从 messages 中提取）
    diagnosis_trajectory = []
    
    for msg in state["messages"]:
        if isinstance(msg, AIMessage):
            # AI 的思考内容
            if msg.content and msg.content.strip():
                diagnosis_trajectory.append(f"[AI Thought]: {msg.content}")
            
            # AI 的工具调用
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", "unknown_tool")
                    tool_args = tc.get("args", {})
                    diagnosis_trajectory.append(
                        f"[AI Action]: {tool_name}({', '.join(f'{k}={v}' for k, v in tool_args.items())})"
                    )
        
        elif isinstance(msg, ToolMessage):
            # 工具执行结果
            tool_name = msg.name
            tool_output = msg.content[:200]  # 截断过长输出
            diagnosis_trajectory.append(f"[Tool Observation ({tool_name})]: {tool_output}")
    
    # 拼接完整轨迹
    full_trajectory = "\n".join(diagnosis_trajectory)
    
    # 3. 调用 LLM 提炼关键步骤（结构化输出）
    print("🤖 [Summary] 正在调用 LLM 提炼关键诊断步骤...")
    
    llm = load_model(backend_model=state["backend_model"])
    
    extraction_prompt = f"""你是网络故障诊断经验总结专家。请从以下完整诊断轨迹中提炼出**关键排查步骤**。

【任务要求】
1. 只保留对定位故障至关重要的步骤（去除冗余、失败的尝试）
2. 每个步骤包含三部分：[Thought]（思考）、[Action]（工具调用）、[Observation]（关键发现）
3. 输出格式必须严格遵循示例，每个步骤占3行
4. 最多保留 5 个关键步骤

【完整诊断轨迹】
{full_trajectory}

【期望输出格式示例】
[Thought]: 首先检查全局连通性，确认故障范围
[Action]: get_reachability()
[Observation]: 发现 h1 无法 ping 通 h3、h4，但可以 ping 通 h2

[Thought]: 怀疑 r1 路由器配置问题，检查路由表
[Action]: node_execute(r1, "ip route show")
[Observation]: 发现缺少 192.168.3.0/24 和 192.168.4.0/24 的路由条目

[Thought]: 检查 OSPF 接口状态，排查动态路由
[Action]: node_execute(r1, "vtysh -c 'show ip ospf interface'")
[Observation]: 发现接口 eth2 被配置为 passive-interface，停止发送 Hello 报文

【当前诊断场景】
- 网络场景: {state["lab_name"]}
- 用户投诉: {state["problem_info"]}
- 故障表现: {state["fault_symptom"]}
- 确诊根因: {state["diagnosis_result"]}
- 故障位置: {state["fault_location"]}

请严格按照上述格式输出关键步骤（不要添加任何额外说明或标题）：
"""
    
    try:
        extraction_response = await llm.ainvoke([HumanMessage(content=extraction_prompt)])
        key_actions_str = extraction_response.content.strip()
        
        # 验证输出格式（简单检查是否包含必要的标记）
        if "[Thought]:" not in key_actions_str or "[Action]:" not in key_actions_str:
            print("⚠️ [Summary] LLM 输出格式异常，使用原始轨迹摘要")
            # 兜底：手动提取前 10 条记录
            key_actions_str = "\n".join(diagnosis_trajectory[:30])
        
        print(f"✅ [Summary] 关键步骤提炼完成，长度: {len(key_actions_str)} 字符")
        print(f"\n【提炼结果预览】\n{key_actions_str[:300]}...\n")
        
    except Exception as e:
        print(f"❌ [Summary] LLM 提炼失败: {e}")
        # 兜底：使用原始轨迹的前30条
        key_actions_str = "\n".join(diagnosis_trajectory[:30])
    
    # 4. 写入 MySQL 数据库
    print("💾 [Summary] 正在将经验写入 MySQL...")
    
    mysql_db = DiagnoseExperienceBase()
    
    # 构建 fuzzy_complaint（结合用户投诉和故障表现）
    fuzzy_complaint = f"{state['problem_info']} (表现: {state['fault_symptom']})"
    
    try:
        await mysql_db.insert_case(
            lab_name=state["lab_name"],
            fuzzy_complaint=fuzzy_complaint,
            root_cause=state["diagnosis_result"],
            key_actions=key_actions_str
        )
        
        print(f"✅ [Summary] 经验已成功写入数据库")
        print(f"   - 场景: {state['lab_name']}")
        print(f"   - 故障表现: {state['fault_symptom']}")
        print(f"   - 根本原因: {state['diagnosis_result']}")
        print(f"   - 故障位置: {state['fault_location']}")
        print(f"   - 关键步骤: {len(key_actions_str)} 字符")
        
    except Exception as e:
        print(f"❌ [Summary] 写入数据库失败: {e}")
        import traceback
        traceback.print_exc()
    
    return {}


# ==========================================
# 4. 路由逻辑
# ==========================================
def should_continue(state: DiagnoseState) -> Literal["tool_filter_node", "summary_node"]:
    """
    决定下一步走向
    
    规则：
    1. 若上一步有工具调用 → 执行工具
    2. 若诊断成功（submit_diagnosis 已调用）→ 总结经验
    3. 若达到最大步数或超时 → 总结经验
    4. 其他情况 → 总结经验（兜底）
    """
    last_msg = state["messages"][-1]
    
    # 【修改】使用标志位简化判断
    if state.get("location_correct", False) and state.get("attribution_correct", False):
        print("\n✅ [Router] 诊断成功（位置+归因均正确），进入总结阶段")
        return "summary_node"
    
    # 检查是否超时或超步数
    current_time = time.time()
    elapsed_time = current_time - state["start_time"]
    
    if elapsed_time > state["time_limit"]:
        print(f"\n⏰ [Router] 诊断超时（{elapsed_time:.2f}秒 > {state['time_limit']}秒），强制进入总结")
        return "summary_node"
    
    if state["tool_call_count"] >= state["max_steps"]:
        print(f"\n🚫 [Router] 达到最大步数（{state['tool_call_count']} >= {state['max_steps']}），强制进入总结")
        return "summary_node"
    
    # 检查是否有工具调用
    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
        print(f"\n🔄 [Router] 检测到工具调用，进入工具执行节点")
        return "tool_filter_node"
    
    # 其他情况（LLM 输出了纯文本，没有工具调用）
    print(f"\n⚠️ [Router] LLM 未生成工具调用，进入总结阶段")
    return "summary_node"


# ==========================================
# 5. 构建诊断子图
# ==========================================
def build_diagnose_graph():
    """
    构建故障诊断 LangGraph
    
    流程：
    START → 全局巡检 → 经验提取 → 诊断专家 ⇄ 工具执行 → 总结 → END
    
    返回：
    编译后的 StateGraph
    """
    workflow = StateGraph(DiagnoseState)
    
    # 添加节点
    workflow.add_node("global_inspector", global_inspector_node)
    workflow.add_node("experience_planner", experience_planner_node)
    workflow.add_node("diagnosis_expert", diagnosis_expert_node)
    workflow.add_node("tool_filter", tool_filter_node)
    workflow.add_node("summary", summary_node)
    
    # 添加边
    workflow.add_edge(START, "global_inspector")
    workflow.add_edge("global_inspector", "experience_planner")
    workflow.add_edge("experience_planner", "diagnosis_expert")
    
    # 条件边：诊断专家 → 工具执行 或 总结
    workflow.add_conditional_edges(
        "diagnosis_expert",
        should_continue,
        {
            "tool_filter_node": "tool_filter",
            "summary_node": "summary"
        }
    )
    
    # 工具执行后回到诊断专家（形成循环）
    workflow.add_edge("tool_filter", "diagnosis_expert")
    
    # 总结后结束
    workflow.add_edge("summary", END)
    
    return workflow.compile()


# ==========================================
# 6. 主入口函数
# ==========================================
async def diagnose_fault(
    lab_name: str,
    netenv_info: str,
    problem_info: str,
    expected_fault: str,
    expected_location: str,
    backend_model: str = "qwen3.5-27b",
    max_steps: int = 20,
    time_limit: float = 300.0,
) -> dict:
    """
    故障诊断主入口
    
    参数：
    - lab_name: 网络场景名称
    - netenv_info: 网络拓扑信息
    - problem_info: 用户投诉
    - expected_fault: 期待的故障
    - expected_location: 期待的故障位置
    - backend_model: 后端 LLM 模型
    - max_steps: 最大执行步数
    - time_limit: 最大执行时间（秒）
    
    返回：
    - dict: 包含诊断结果、执行统计等信息
    """
    print("\n" + "="*80)
    print("🚀 故障诊断智能体启动".center(80))
    print("="*80)
    print(f"场景: {lab_name}")
    print(f"模型: {backend_model}")
    print(f"限制: 最多 {max_steps} 步，最长 {time_limit} 秒")
    print("="*80)
    
    # 初始化状态
    initial_state = {
        "lab_name": lab_name,
        "netenv_info": netenv_info,
        "problem_info": problem_info,
        "backend_model": backend_model,
        "max_steps": max_steps,
        "time_limit": time_limit,
        "global_ping_summary": "",
        "fault_symptom": "",
        "knowledge_context": "",
        "messages": [],
        # 👇 就是漏了这最关键的两行 👇
        "expected_fault": expected_fault,       
        "expected_location": expected_location,   
        #     
        "fault_location": "",
        "diagnosis_result": "",
        "location_correct": False,      # 【新增】
        "attribution_correct": False,   # 【新增】
        "tool_call_count": 0,
        "execution_time": 0.0,
        "token_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        },
        "start_time": time.time()
    }
    
    # 构建并运行图
    graph = build_diagnose_graph()
    
    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        print(f"\n❌ 诊断过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        final_state = initial_state
        final_state["diagnosis_result"] = f"ERROR: {str(e)}"
    finally:
        # 清理 MCP Client 资源
        await cleanup_mcp_client()
    
    # 计算总执行时间
    final_state["execution_time"] = time.time() - final_state["start_time"]
    
    # 打印诊断报告
    print("\n" + "="*80)
    print("📊 诊断报告".center(80))
    print("="*80)
    print(f"诊断结果: {'✅ 成功' if final_state.get("expected_fault") == final_state.get("diagnosis_result") and final_state.get("expected_location") == final_state.get("fault_location") else '❌ 失败'}")
    print(f"故障位置: {final_state['fault_location']}")
    print(f"故障根因: {final_state['diagnosis_result']}")
    print(f"执行步数: {final_state['tool_call_count']} / {max_steps}")
    print(f"执行时间: {final_state['execution_time']:.2f}秒 / {time_limit}秒")
    print(f"Token 消耗: {final_state['token_usage']['total_tokens']} tokens")
    print(f"  - 输入: {final_state['token_usage']['input_tokens']}")
    print(f"  - 输出: {final_state['token_usage']['output_tokens']}")
    print("="*80)
    
    return {
        "location_correct": final_state.get("location_correct", False),    # 【新增】
        "attribution_correct": final_state.get("attribution_correct", False),  # 【新增】        
        "fault_location": final_state["fault_location"],
        "diagnosis_result": final_state["diagnosis_result"],
        "tool_call_count": final_state["tool_call_count"],
        "execution_time": final_state["execution_time"],
        "token_usage": final_state["token_usage"]
    }