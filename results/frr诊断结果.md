======================================================================
🧪 [开始自动化测试套件]: FRR 类故障 (Frr Faults)
📍 测试场景: static_routing
📝 包含用例: 3 个
======================================================================


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 1/3]: inject_route_missing
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_route_missing] -> 预期: [route_missing]
==================================================
[System] 🛠️  正在部署网络拓扑 (static_routing via static_routing.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:25:25 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:25:25 [INFO] SystemLogger: Injecting fault: inject_route_missing ...

[Inject Pool] 正在为 static_routing 下发 SERVICE 故障: inject_route_missing
2026-03-16 02:25:25 [INFO] SystemLogger: 正在注入故障: r1 删除目标网段路由 192.168.4.0/24
2026-03-16 02:25:27 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 static_routing 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tos1_1(192.168.1.2) | 默认网关: 192.168.1.1
- h2 [host] | 接口: tos1_1(192.168.1.3) | 默认网关: 192.168.1.1
- h3 [host] | 接口: tos2_1(192.168.2.2) | 默认网关: 192.168.2.1
- h4 [host] | 接口: tos3_1(192.168.3.2) | 默认网关: 192.168.3.1
- h5 [host] | 接口: tos4_1(192.168.4.2) | 默认网关: 192.168.4.1
- h6 [host] | 接口: tos4_1(192.168.4.3) | 默认网关: 192.168.4.1
- r1 [router] | 接口: tos1_1(192.168.1.1), tos2_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: tos3_1(192.168.3.1), tos4_1(192.168.4.1), tor1_1(192.168.0.2)
- s1 [switch]
- s2 [switch]
- s3 [switch]
- s4 [switch]

[链路]
- 链路 l1: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 l10: s4 <---> h5(192.168.4.2)
- 链路 l11: s4 <---> h6(192.168.4.3)
- 链路 l2: r1(192.168.1.1) <---> s1
- 链路 l3: r1(192.168.2.1) <---> s2
- 链路 l4: r2(192.168.3.1) <---> s3
- 链路 l5: r2(192.168.4.1) <---> s4
- 链路 l6: s1 <---> h1(192.168.1.2)
- 链路 l7: s1 <---> h2(192.168.1.3)
- 链路 l8: s2 <---> h3(192.168.2.2)
- 链路 l9: s3 <---> h4(192.168.3.2)

【当前故障】
用户投诉: 主机 h1 无法正常 Ping 通节点 192.168.4.2，网络完全不可达，疑似路由问题。

严格遵循 ReAct 框架诊断网络故障。注意你只有 50 次尝试机会!

【专家经验】
- 防Ping陷阱：
  如果用户投诉“网络卡顿、慢” 或者 “不稳定”，但你发现 Ping 测试竟然是 0% 丢包且低延迟，不要被骗了！
  必须立刻使用 `check_link_bandwidth` 或 `check_cpu_overload` 检查主机 CPU占用，或核心路由器或网关的带宽限制规则！
- 二层/三层网络隔离法则（极其重要！）：
  1. 仅在 static_routing, simple_bgp, ospf_enterprise, rip_internet 场景（包含 r1, r2 路由器）中，才能使用 `check_routing_table` 和 `check_data_plane_drop` 查路由和防火墙！
  2. 对于 sdn_openflow 和 p4_star 场景，节点 s0, s1, s2 等都是二层交换机，绝对没有三层 IP 路由表！严禁在它们上面查路由，否则会得到 "Network is unreachable" 的假象！
- SDN 路径追踪法则：
  在 sdn_openflow 场景中如果 Ping 不通，并且检查第一个交换机发现控制器连接正常且流表正常，**千万不要放弃！** 故障很可能发生在接入层交换机（例如连接 Host 的 s1, s2等）。你必须依次调用 `check_ovs_status` 检查链路途经的**所有交换机**，直到找出流表丢失 (drop) 或 控制器断开 (is_connected 消失) 的节点。

【工作流规范】
1. Observation (观察现象)：分析当前网络状态、存在故障和之前的工具返回信息;
2. Thought (思考假设)：基于已有信息，提出可能的故障原因，并计划下一步的排查动作;
3. Action (调用工具)：一次调用 1 个适当的 MCP 工具来验证你的假设; 
4. 循环上述过程最多 50 次，找到根本原因，次数用完的话就直接提交你认为的最可能的结果就行;
5. 提交结果：确定根本原因后，必须且仅调用一次 `submit_diagnosis` 工具来结束任务。

【网络场景说明】
1. static_routing: 静态路由, 可能发生主机侧故障、物理链路故障、通用 frr 故障(优先考虑)
2. simple_bgp: 简单 BGP 网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、bgp协议故障(优先考虑)
3. ospf_enterprise: OSPF 企业网, 可能发生主机侧故障、物理链路故障、通用 frr 故障、ospf协议故障(优先考虑)
4. rip_internet: rip 小型网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、rip协议故障(优先考虑)
5. sdn_openflow: sdn 网络, 可能发生主机侧故障、物理链路故障、ovs或ryu故障(优先考虑)
6. p4_star: P4 星型网络, 可能发生主机侧故障、物理链路故障、p4-bmv2故障(优先考虑)

【根本原因说明】
你必须且仅能从以下 3 大类中选择一个最符合的英文字符串作为最终诊断结果提交。请仔细区分故障发生的载体（是主机配置出错，还是中间的路由器/交换机出错）：

1. 主机侧故障 (Host Faults) - 仅限端主机(Host)自身的配置问题：
  - ip_misconfig: 主机网卡 IP 地址或子网掩码配置错误、甚至未配置
  - default_route_missing: 主机自身的路由表中缺少默认网关路由(default via)
  - arp_poisoning: 主机自身的 ARP 缓存表被投毒，网关 MAC 地址被恶意篡改
  - interface_down: 主机的物理或逻辑网络接口处于 DOWN 状态
  - dns_error: 主机的 DNS 服务器配置错误，导致无法解析域名
  - high_cpu_load: 主机 CPU 占用率极高（如满载），导致发包或处理极慢

2. 核心网络服务故障 (Service Faults) - 发生在中间节点(Router/Switch)上的路由协议或数据面问题：
(1) 通用 frr 故障:
  - route_missing: 路由器(Router)的全局路由表中丢失了去往目标网段的路由
  - static_route_blackhole: 路由器上被人为配置了去往目标网段的黑洞路由 (blackhole)
  - router_data_plane_drop: 路由器的防火墙或 iptables 规则 (FORWARD链) 强行 DROP/REJECT 了转发流量
(2) bgp协议故障(仅针对 simple_bgp 场景):
  - bgp_neighbor_shutdown: 路由器的 BGP 邻居关系被断开/关闭 (Active/Idle状态)
  - bgp_withdraw_route: BGP 路由撤销，导致 BGP 表中无目标路由
  - bgp_wrong_peer_asn: BGP 邻居的 AS 号配置错误导致无法建联
(3) ospf协议故障(仅针对 ospf_enterprise 场景):
  - ospf_passive_interface: 路由器的接口被设置为 OSPF 被动接口，停止发送 Hello 包
  - ospf_cost_spike: OSPF 接口的开销 (Cost) 被恶意调得极高，导致流量绕路或中断
  - ospf_daemon_crash: 路由器的 OSPF 进程崩溃退出
(4) rip协议故障(仅针对 rip_internet 场景):
  - rip_passive_interface: 路由器的接口被设置为 RIP 被动接口，停止发送更新
  - rip_route_filter: 路由器被恶意配置了 distribute-list 规则，强行过滤了路由发布
  - rip_metric_offset: 路由器被恶意配置了 offset-list，大幅篡改路由跳数导致不可达
(5) ovs或ryu故障(仅针对 sdn_openflow 场景):
  - sdn_controller_crash: SDN 控制器(Ryu)宕机或断开连接
  - ovs_disconnect_controller: OpenvSwitch 与 SDN 控制器断开连接
  - ovs_global_drop_flow: OpenvSwitch 被下发了全局 Drop 所有流表
(6) p4-bmv2故障(仅针对 p4_star 场景):
  - bmv2_process_crash: P4 Bmv2 交换机进程崩溃
  - p4_table_drop: P4 交换机匹配到丢弃流表项
  - p4_wrong_forwarding: P4 交换机转发逻辑或端口映射错误

3. 物理链路故障 (Link Faults) - 连接各节点之间的网线/通道质量恶化：
  - link_latency: 链路上被人为注入了异常高且稳定的延迟
  - link_loss: 链路存在明显的报文丢包率 (Packet Loss > 0%)
  - link_jitter: 链路延迟极不稳定，出现严重抖动 (Jitter/mdev 很大)
  - link_bandwidth: 链路可用带宽被严格限制 (如 TBF 限速)，导致大流量严重拥堵

【严禁行为】
- ⚠️ 得出最终的故障结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_diagnosis` 工具并传入根本原因，只有这样系统才能接收到你的答案！
- 遇到信息不足时，务必先通过工具查询状态，绝不可随意猜测
- 次数很多，切不可仅用一个工具就下定论！
- 切勿一次性调用大量不相关的工具，应按照逻辑链条一步一步排查
- 所有工具输出结果都是稳定正确的，同样的工具+同样的输入参数切勿调用两次以上！

======================================================================
2026-03-16 02:25:27 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:25:27 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:25:36 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 无法 Ping 通 192.168.4.2 的问题。这是一个 static_routing 场景，涉及跨网段通信。

首先，让我从 h1 向目标 IP 进行 Ping 测试，确认故障现象。
2026-03-16 02:25:36 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.4.2'}
2026-03-16 02:25:48 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.4.2 (192.168.4.2) 56(84) bytes of data.
From 192.168.1.1 icmp_seq=1 Destination Net Unreachable
From 192.168.1.1 icmp_seq=2 Destination Net Unreachable
From 192.168.1.1 icmp_seq=3 Destination Net Unreachable
From 192.168.1.1 icmp_seq=4 Destination Net Unreachable

--- 192.168.4.2 ping statistics ---
10 packets transmitted, 0 received, +4 errors, 100% packet loss, time 9196ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:01 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
Ping 结果显示 "Destination Net Unreachable"，并且是从 192.168.1.1（h1 的默认网关）返回的错误。这表明 h1 能够将数据包发送到网关，但网关无法将数据包转发到目标网络。

这是一个跨网段通信问题：
- h1 在 192.168.1.0/24 网段
- 目标 192.168.4.2 在 192.168.4.0/24 网段

数据包路径应该是：h1 -> r1 -> r2 -> h5

让我先检查 h1 的配置是否正常，包括 IP 配置和默认路由。
2026-03-16 02:26:01 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_ip_misconfig'
   📥 输入参数: {'host': 'h1', 'iface': 'tos1_1'}
2026-03-16 02:26:01 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_ip_misconfig)
   📤 结果详情:
3: tos1_1@if7: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether e6:12:e6:a0:60:6d brd ff:ff:ff:ff:ff:ff link-netnsid 1
    inet 192.168.1.2/24 brd 192.168.1.255 scope global tos1_1
       valid_lft forever preferred_lft forever
    inet6 fe80::e412:e6ff:fea0:606d/64 scope link 
       valid_lft forever preferred_lft forever
[专家提示] 请核对上述输出的IPv4地址 192.168.1.2/24 是否与【网络拓扑信息】中 h1 的接口 IP 一致，若不一致，调用 submit_diagnosis 提交 ip_misconfig。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:04 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的 IP 配置正确（192.168.1.2/24），与拓扑信息一致。接下来检查 h1 的默认路由是否存在。
2026-03-16 02:26:04 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_default_route_missing'
   📥 输入参数: {'host': 'h1'}
2026-03-16 02:26:05 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_default_route_missing)
   📤 结果详情:
default via 192.168.1.1 dev tos1_1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.2
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:09 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的默认路由配置正确，指向 192.168.1.1（r1）。问题可能出在路由器 r1 或 r2 上。

由于这是 static_routing 场景，我需要检查路由器的路由表。首先检查 r1 是否有去往 192.168.4.0/24 网段的路由。
2026-03-16 02:26:09 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r1', 'target_ip': '192.168.4.2'}
2026-03-16 02:26:10 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor2_1 proto kernel scope link src 192.168.0.1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.1 
192.168.2.0/24 dev tos2_1 proto kernel scope link src 192.168.2.1 
192.168.3.0/24 via 192.168.0.2 dev tor2_1

【内核路由匹配测试 (ip route get 192.168.4.2)】:
RTNETLINK answers: Network is unreachable

[系统警告] 内核反馈无法找到目标路由。确诊为静态路由缺失，请检查是否是 route_missing。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:20 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
发现问题了！r1 的路由表中：
- 有 192.168.0.0/24（直连）
- 有 192.168.1.0/24（直连）
- 有 192.168.2.0/24（直连）
- 有 192.168.3.0/24 via 192.168.0.2（通过 r2）

但是**没有 192.168.4.0/24 的路由**！r1 不知道如何到达 192.168.4.0/24 网段。

让我再检查 r2 的路由表，确认 r2 是否有正确的路由配置。
2026-03-16 02:26:20 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r2', 'target_ip': '192.168.4.2'}
2026-03-16 02:26:21 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor1_1 proto kernel scope link src 192.168.0.2 
192.168.1.0/24 via 192.168.0.1 dev tor1_1 
192.168.2.0/24 via 192.168.0.1 dev tor1_1 
192.168.3.0/24 dev tos3_1 proto kernel scope link src 192.168.3.1 
192.168.4.0/24 dev tos4_1 proto kernel scope link src 192.168.4.1

【内核路由匹配测试 (ip route get 192.168.4.2)】:
192.168.4.2 dev tos4_1 src 192.168.4.1 uid 0 
    cache

[专家提示] 内核成功匹配到了去往 192.168.4.2 的正向路由。
[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:34 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
r2 的路由表是正确的：
- r2 有 192.168.4.0/24 的直连路由（通过 tos4_1）
- r2 也有去往 192.168.1.0/24 和 192.168.2.0/24 的路由（通过 r1）

问题在于 **r1 缺少去往 192.168.4.0/24 网段的路由**。r1 只有：
- 直连的 192.168.0.0/24, 192.168.1.0/24, 192.168.2.0/24
- 通过 r2 的 192.168.3.0/24

但缺少 192.168.4.0/24 的路由。这是一个典型的 **route_missing** 故障。

让我再确认一下，检查 r1 是否有数据面 DROP 规则（虽然路由缺失已经很明显了）。
2026-03-16 02:26:34 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_data_plane_drop'
   📥 输入参数: {'router': 'r1'}
2026-03-16 02:26:35 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_data_plane_drop)
   📤 结果详情:
Chain FORWARD (policy ACCEPT)
target     prot opt source               destination
[专家分析] FORWARD 链全为 ACCEPT，数据平面未阻断流量。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:26:45 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
确认 r1 的防火墙规则没有问题（FORWARD 链是 ACCEPT）。

故障原因已经很明确了：
- h1 配置正确（IP 和默认路由都正常）
- r2 路由表正确（有去往所有网段的路由）
- **r1 缺少去往 192.168.4.0/24 网段的路由**

当 h1 发送数据包到 192.168.4.2 时：
1. h1 将数据包发送到默认网关 192.168.1.1（r1）
2. r1 查找路由表，发现没有去往 192.168.4.0/24 的路由
3. r1 返回 "Destination Net Unreachable" 给 h1

这是一个典型的 **route_missing** 故障，发生在路由器 r1 上。
2026-03-16 02:26:45 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'route_missing'}
2026-03-16 02:26:45 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: route_missing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:26:54 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障根本原因是 **route_missing**（路由缺失）。

**故障总结：**
- 主机 h1 无法 Ping 通 192.168.4.2
- h1 的 IP 配置和默认路由均正确
- 路由器 r2 的路由表完整，包含所有必要路由
- **路由器 r1 缺少去往 192.168.4.0/24 网段的静态路由**
- 当 h1 发送数据包到 192.168.4.2 时，r1 无法找到匹配的路由，返回 "Destination Net Unreachable"

这是一个典型的静态路由配置缺失问题，需要在 r1 上添加一条指向 192.168.4.0/24 网段的路由（下一跳应为 192.168.0.2，即 r2）。
2026-03-16 02:26:54 [INFO] SystemLogger: Agent Diagnosis Finished. Result: route_missing

📊 [测试结果评估]
预期 Root Cause: route_missing
Agent 诊断结论: route_missing
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (static_routing)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 2/3]: inject_static_route_blackhole
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_static_route_blackhole] -> 预期: [static_route_blackhole]
==================================================
[System] 🛠️  正在部署网络拓扑 (static_routing via static_routing.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:28:15 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:28:15 [INFO] SystemLogger: Injecting fault: inject_static_route_blackhole ...

[Inject Pool] 正在为 static_routing 下发 SERVICE 故障: inject_static_route_blackhole
2026-03-16 02:28:15 [INFO] SystemLogger: 正在注入故障: r1 黑洞路由 192.168.4.0/24
2026-03-16 02:28:18 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 static_routing 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tos1_1(192.168.1.2) | 默认网关: 192.168.1.1
- h2 [host] | 接口: tos1_1(192.168.1.3) | 默认网关: 192.168.1.1
- h3 [host] | 接口: tos2_1(192.168.2.2) | 默认网关: 192.168.2.1
- h4 [host] | 接口: tos3_1(192.168.3.2) | 默认网关: 192.168.3.1
- h5 [host] | 接口: tos4_1(192.168.4.2) | 默认网关: 192.168.4.1
- h6 [host] | 接口: tos4_1(192.168.4.3) | 默认网关: 192.168.4.1
- r1 [router] | 接口: tos1_1(192.168.1.1), tos2_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: tos3_1(192.168.3.1), tos4_1(192.168.4.1), tor1_1(192.168.0.2)
- s1 [switch]
- s2 [switch]
- s3 [switch]
- s4 [switch]

[链路]
- 链路 l1: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 l10: s4 <---> h5(192.168.4.2)
- 链路 l11: s4 <---> h6(192.168.4.3)
- 链路 l2: r1(192.168.1.1) <---> s1
- 链路 l3: r1(192.168.2.1) <---> s2
- 链路 l4: r2(192.168.3.1) <---> s3
- 链路 l5: r2(192.168.4.1) <---> s4
- 链路 l6: s1 <---> h1(192.168.1.2)
- 链路 l7: s1 <---> h2(192.168.1.3)
- 链路 l8: s2 <---> h3(192.168.2.2)
- 链路 l9: s3 <---> h4(192.168.3.2)

【当前故障】
用户投诉: 主机 h1 无法正常 Ping 通节点 192.168.4.2，网络完全不可达，疑似路由问题。

严格遵循 ReAct 框架诊断网络故障。注意你只有 50 次尝试机会!

【专家经验】
- 防Ping陷阱：
  如果用户投诉“网络卡顿、慢” 或者 “不稳定”，但你发现 Ping 测试竟然是 0% 丢包且低延迟，不要被骗了！
  必须立刻使用 `check_link_bandwidth` 或 `check_cpu_overload` 检查主机 CPU占用，或核心路由器或网关的带宽限制规则！
- 二层/三层网络隔离法则（极其重要！）：
  1. 仅在 static_routing, simple_bgp, ospf_enterprise, rip_internet 场景（包含 r1, r2 路由器）中，才能使用 `check_routing_table` 和 `check_data_plane_drop` 查路由和防火墙！
  2. 对于 sdn_openflow 和 p4_star 场景，节点 s0, s1, s2 等都是二层交换机，绝对没有三层 IP 路由表！严禁在它们上面查路由，否则会得到 "Network is unreachable" 的假象！
- SDN 路径追踪法则：
  在 sdn_openflow 场景中如果 Ping 不通，并且检查第一个交换机发现控制器连接正常且流表正常，**千万不要放弃！** 故障很可能发生在接入层交换机（例如连接 Host 的 s1, s2等）。你必须依次调用 `check_ovs_status` 检查链路途经的**所有交换机**，直到找出流表丢失 (drop) 或 控制器断开 (is_connected 消失) 的节点。

【工作流规范】
1. Observation (观察现象)：分析当前网络状态、存在故障和之前的工具返回信息;
2. Thought (思考假设)：基于已有信息，提出可能的故障原因，并计划下一步的排查动作;
3. Action (调用工具)：一次调用 1 个适当的 MCP 工具来验证你的假设; 
4. 循环上述过程最多 50 次，找到根本原因，次数用完的话就直接提交你认为的最可能的结果就行;
5. 提交结果：确定根本原因后，必须且仅调用一次 `submit_diagnosis` 工具来结束任务。

【网络场景说明】
1. static_routing: 静态路由, 可能发生主机侧故障、物理链路故障、通用 frr 故障(优先考虑)
2. simple_bgp: 简单 BGP 网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、bgp协议故障(优先考虑)
3. ospf_enterprise: OSPF 企业网, 可能发生主机侧故障、物理链路故障、通用 frr 故障、ospf协议故障(优先考虑)
4. rip_internet: rip 小型网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、rip协议故障(优先考虑)
5. sdn_openflow: sdn 网络, 可能发生主机侧故障、物理链路故障、ovs或ryu故障(优先考虑)
6. p4_star: P4 星型网络, 可能发生主机侧故障、物理链路故障、p4-bmv2故障(优先考虑)

【根本原因说明】
你必须且仅能从以下 3 大类中选择一个最符合的英文字符串作为最终诊断结果提交。请仔细区分故障发生的载体（是主机配置出错，还是中间的路由器/交换机出错）：

1. 主机侧故障 (Host Faults) - 仅限端主机(Host)自身的配置问题：
  - ip_misconfig: 主机网卡 IP 地址或子网掩码配置错误、甚至未配置
  - default_route_missing: 主机自身的路由表中缺少默认网关路由(default via)
  - arp_poisoning: 主机自身的 ARP 缓存表被投毒，网关 MAC 地址被恶意篡改
  - interface_down: 主机的物理或逻辑网络接口处于 DOWN 状态
  - dns_error: 主机的 DNS 服务器配置错误，导致无法解析域名
  - high_cpu_load: 主机 CPU 占用率极高（如满载），导致发包或处理极慢

2. 核心网络服务故障 (Service Faults) - 发生在中间节点(Router/Switch)上的路由协议或数据面问题：
(1) 通用 frr 故障:
  - route_missing: 路由器(Router)的全局路由表中丢失了去往目标网段的路由
  - static_route_blackhole: 路由器上被人为配置了去往目标网段的黑洞路由 (blackhole)
  - router_data_plane_drop: 路由器的防火墙或 iptables 规则 (FORWARD链) 强行 DROP/REJECT 了转发流量
(2) bgp协议故障(仅针对 simple_bgp 场景):
  - bgp_neighbor_shutdown: 路由器的 BGP 邻居关系被断开/关闭 (Active/Idle状态)
  - bgp_withdraw_route: BGP 路由撤销，导致 BGP 表中无目标路由
  - bgp_wrong_peer_asn: BGP 邻居的 AS 号配置错误导致无法建联
(3) ospf协议故障(仅针对 ospf_enterprise 场景):
  - ospf_passive_interface: 路由器的接口被设置为 OSPF 被动接口，停止发送 Hello 包
  - ospf_cost_spike: OSPF 接口的开销 (Cost) 被恶意调得极高，导致流量绕路或中断
  - ospf_daemon_crash: 路由器的 OSPF 进程崩溃退出
(4) rip协议故障(仅针对 rip_internet 场景):
  - rip_passive_interface: 路由器的接口被设置为 RIP 被动接口，停止发送更新
  - rip_route_filter: 路由器被恶意配置了 distribute-list 规则，强行过滤了路由发布
  - rip_metric_offset: 路由器被恶意配置了 offset-list，大幅篡改路由跳数导致不可达
(5) ovs或ryu故障(仅针对 sdn_openflow 场景):
  - sdn_controller_crash: SDN 控制器(Ryu)宕机或断开连接
  - ovs_disconnect_controller: OpenvSwitch 与 SDN 控制器断开连接
  - ovs_global_drop_flow: OpenvSwitch 被下发了全局 Drop 所有流表
(6) p4-bmv2故障(仅针对 p4_star 场景):
  - bmv2_process_crash: P4 Bmv2 交换机进程崩溃
  - p4_table_drop: P4 交换机匹配到丢弃流表项
  - p4_wrong_forwarding: P4 交换机转发逻辑或端口映射错误

3. 物理链路故障 (Link Faults) - 连接各节点之间的网线/通道质量恶化：
  - link_latency: 链路上被人为注入了异常高且稳定的延迟
  - link_loss: 链路存在明显的报文丢包率 (Packet Loss > 0%)
  - link_jitter: 链路延迟极不稳定，出现严重抖动 (Jitter/mdev 很大)
  - link_bandwidth: 链路可用带宽被严格限制 (如 TBF 限速)，导致大流量严重拥堵

【严禁行为】
- ⚠️ 得出最终的故障结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_diagnosis` 工具并传入根本原因，只有这样系统才能接收到你的答案！
- 遇到信息不足时，务必先通过工具查询状态，绝不可随意猜测
- 次数很多，切不可仅用一个工具就下定论！
- 切勿一次性调用大量不相关的工具，应按照逻辑链条一步一步排查
- 所有工具输出结果都是稳定正确的，同样的工具+同样的输入参数切勿调用两次以上！

======================================================================
2026-03-16 02:28:18 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:28:18 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:28:22 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 无法 Ping 通 192.168.4.2 的问题。这是一个 static_routing 场景，涉及跨网段通信。

首先，让我从 h1 向目标 IP 进行 Ping 测试，确认故障现象。
2026-03-16 02:28:22 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.4.2'}
2026-03-16 02:28:34 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.4.2 (192.168.4.2) 56(84) bytes of data.

--- 192.168.4.2 ping statistics ---
10 packets transmitted, 0 received, 100% packet loss, time 9196ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:28:45 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
确认了故障：h1 到 192.168.4.2 的 Ping 测试 100% 丢包，网络完全不可达。

这是一个跨网段通信问题（h1 在 192.168.1.0/24 网段，目标 192.168.4.2 在 192.168.4.0/24 网段）。我需要逐步排查：

1. 首先检查 h1 自身的配置（IP、默认路由、接口状态）
2. 然后检查中间路由器的路由表
3. 检查是否有防火墙规则阻止流量

让我先检查 h1 的 IP 配置是否正确：
2026-03-16 02:28:45 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_ip_misconfig'
   📥 输入参数: {'host': 'h1', 'iface': 'tos1_1'}
2026-03-16 02:28:46 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_ip_misconfig)
   📤 结果详情:
3: tos1_1@if6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether da:02:8c:24:01:fc brd ff:ff:ff:ff:ff:ff link-netnsid 1
    inet 192.168.1.2/24 brd 192.168.1.255 scope global tos1_1
       valid_lft forever preferred_lft forever
    inet6 fe80::d802:8cff:fe24:1fc/64 scope link 
       valid_lft forever preferred_lft forever
[专家提示] 请核对上述输出的IPv4地址 192.168.1.2/24 是否与【网络拓扑信息】中 h1 的接口 IP 一致，若不一致，调用 submit_diagnosis 提交 ip_misconfig。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:28:48 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的 IP 配置正确（192.168.1.2/24），与拓扑信息一致。

接下来检查 h1 的默认路由是否存在：
2026-03-16 02:28:48 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_default_route_missing'
   📥 输入参数: {'host': 'h1'}
2026-03-16 02:28:49 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_default_route_missing)
   📤 结果详情:
default via 192.168.1.1 dev tos1_1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.2
──────────────────────────────────────────────────────────────────────
2026-03-16 02:28:52 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的默认路由存在，指向 192.168.1.1（r1 的接口），配置正确。

接下来检查 h1 的接口状态是否正常：
2026-03-16 02:28:52 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_interface_down'
   📥 输入参数: {'host': 'h1', 'iface': 'tos1_1'}
2026-03-16 02:28:53 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_interface_down)
   📤 结果详情:
3: tos1_1@if6: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000
    link/ether da:02:8c:24:01:fc brd ff:ff:ff:ff:ff:ff link-netnsid 1
[专家提示] 未发现异常！接口状态良好
──────────────────────────────────────────────────────────────────────
2026-03-16 02:29:01 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的接口状态正常（UP）。

现在问题可能出在中间的路由器上。由于这是 static_routing 场景，我需要检查路由器的路由表。

从拓扑来看，h1 到 192.168.4.2 的路径应该是：
h1 -> r1 (192.168.1.1) -> r2 (通过 192.168.0.0/24 链路) -> s4 -> h5(192.168.4.2)

让我先检查 r1 的路由表，看是否有去往 192.168.4.0/24 网段的路由：
2026-03-16 02:29:01 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r1', 'target_ip': '192.168.4.2'}
2026-03-16 02:29:02 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor2_1 proto kernel scope link src 192.168.0.1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.1 
192.168.2.0/24 dev tos2_1 proto kernel scope link src 192.168.2.1 
192.168.3.0/24 via 192.168.0.2 dev tor2_1 
blackhole 192.168.4.0/24

【内核路由匹配测试 (ip route get 192.168.4.2)】:
RTNETLINK answers: Invalid argument

[专家提示] 内核成功匹配到了去往 192.168.4.2 的正向路由。
[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:29:11 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
发现问题了！r1 的路由表中有一条 `blackhole 192.168.4.0/24` 规则，这意味着去往 192.168.4.0/24 网段的流量被配置为黑洞路由，会被直接丢弃。

这就是导致 h1 无法 Ping 通 192.168.4.2 的根本原因：r1 路由器上配置了去往目标网段 192.168.4.0/24 的黑洞路由。

让我再确认一下，检查 r2 的路由表，看看回程路由是否正常：
2026-03-16 02:29:11 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r2', 'target_ip': '192.168.1.2'}
2026-03-16 02:29:12 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor1_1 proto kernel scope link src 192.168.0.2 
192.168.1.0/24 via 192.168.0.1 dev tor1_1 
192.168.2.0/24 via 192.168.0.1 dev tor1_1 
192.168.3.0/24 dev tos3_1 proto kernel scope link src 192.168.3.1 
192.168.4.0/24 dev tos4_1 proto kernel scope link src 192.168.4.1

【内核路由匹配测试 (ip route get 192.168.1.2)】:
192.168.1.2 via 192.168.0.1 dev tor1_1 src 192.168.0.2 uid 0 
    cache

[专家提示] 内核成功匹配到了去往 192.168.1.2 的正向路由。
[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:29:19 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
r2 的路由表是正常的，它有去往 192.168.1.0/24 网段的路由（via 192.168.0.1），所以回程路由没有问题。

问题明确在 r1 上：r1 配置了 `blackhole 192.168.4.0/24`，这是一个黑洞路由，会导致所有去往 192.168.4.0/24 网段的流量被丢弃。

根据根本原因说明，这属于 **static_route_blackhole**：路由器上被人为配置了去往目标网段的黑洞路由 (blackhole)。

让我提交诊断结果：
2026-03-16 02:29:19 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'static_route_blackhole'}
2026-03-16 02:29:19 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: static_route_blackhole
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:29:21 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障根本原因是 **static_route_blackhole**：r1 路由器上配置了去往目标网段 192.168.4.0/24 的黑洞路由，导致 h1 发往 192.168.4.2 的流量被直接丢弃，无法到达目的地。
2026-03-16 02:29:21 [INFO] SystemLogger: Agent Diagnosis Finished. Result: static_route_blackhole

📊 [测试结果评估]
预期 Root Cause: static_route_blackhole
Agent 诊断结论: static_route_blackhole
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (static_routing)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 3/3]: inject_router_data_plane_drop
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_router_data_plane_drop] -> 预期: [router_data_plane_drop]
==================================================
[System] 🛠️  正在部署网络拓扑 (static_routing via static_routing.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:30:36 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:30:37 [INFO] SystemLogger: Injecting fault: inject_router_data_plane_drop ...

[Inject Pool] 正在为 static_routing 下发 SERVICE 故障: inject_router_data_plane_drop
2026-03-16 02:30:37 [INFO] SystemLogger: 正在注入故障: r1 全局 ICMP 阻断
2026-03-16 02:30:39 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 static_routing 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tos1_1(192.168.1.2) | 默认网关: 192.168.1.1
- h2 [host] | 接口: tos1_1(192.168.1.3) | 默认网关: 192.168.1.1
- h3 [host] | 接口: tos2_1(192.168.2.2) | 默认网关: 192.168.2.1
- h4 [host] | 接口: tos3_1(192.168.3.2) | 默认网关: 192.168.3.1
- h5 [host] | 接口: tos4_1(192.168.4.2) | 默认网关: 192.168.4.1
- h6 [host] | 接口: tos4_1(192.168.4.3) | 默认网关: 192.168.4.1
- r1 [router] | 接口: tos1_1(192.168.1.1), tos2_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: tos3_1(192.168.3.1), tos4_1(192.168.4.1), tor1_1(192.168.0.2)
- s1 [switch]
- s2 [switch]
- s3 [switch]
- s4 [switch]

[链路]
- 链路 l1: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 l10: s4 <---> h5(192.168.4.2)
- 链路 l11: s4 <---> h6(192.168.4.3)
- 链路 l2: r1(192.168.1.1) <---> s1
- 链路 l3: r1(192.168.2.1) <---> s2
- 链路 l4: r2(192.168.3.1) <---> s3
- 链路 l5: r2(192.168.4.1) <---> s4
- 链路 l6: s1 <---> h1(192.168.1.2)
- 链路 l7: s1 <---> h2(192.168.1.3)
- 链路 l8: s2 <---> h3(192.168.2.2)
- 链路 l9: s3 <---> h4(192.168.3.2)

【当前故障】
用户投诉: 主机 h1 无法正常 Ping 通节点 192.168.4.2，网络完全不可达，疑似路由问题。

严格遵循 ReAct 框架诊断网络故障。注意你只有 50 次尝试机会!

【专家经验】
- 防Ping陷阱：
  如果用户投诉“网络卡顿、慢” 或者 “不稳定”，但你发现 Ping 测试竟然是 0% 丢包且低延迟，不要被骗了！
  必须立刻使用 `check_link_bandwidth` 或 `check_cpu_overload` 检查主机 CPU占用，或核心路由器或网关的带宽限制规则！
- 二层/三层网络隔离法则（极其重要！）：
  1. 仅在 static_routing, simple_bgp, ospf_enterprise, rip_internet 场景（包含 r1, r2 路由器）中，才能使用 `check_routing_table` 和 `check_data_plane_drop` 查路由和防火墙！
  2. 对于 sdn_openflow 和 p4_star 场景，节点 s0, s1, s2 等都是二层交换机，绝对没有三层 IP 路由表！严禁在它们上面查路由，否则会得到 "Network is unreachable" 的假象！
- SDN 路径追踪法则：
  在 sdn_openflow 场景中如果 Ping 不通，并且检查第一个交换机发现控制器连接正常且流表正常，**千万不要放弃！** 故障很可能发生在接入层交换机（例如连接 Host 的 s1, s2等）。你必须依次调用 `check_ovs_status` 检查链路途经的**所有交换机**，直到找出流表丢失 (drop) 或 控制器断开 (is_connected 消失) 的节点。

【工作流规范】
1. Observation (观察现象)：分析当前网络状态、存在故障和之前的工具返回信息;
2. Thought (思考假设)：基于已有信息，提出可能的故障原因，并计划下一步的排查动作;
3. Action (调用工具)：一次调用 1 个适当的 MCP 工具来验证你的假设; 
4. 循环上述过程最多 50 次，找到根本原因，次数用完的话就直接提交你认为的最可能的结果就行;
5. 提交结果：确定根本原因后，必须且仅调用一次 `submit_diagnosis` 工具来结束任务。

【网络场景说明】
1. static_routing: 静态路由, 可能发生主机侧故障、物理链路故障、通用 frr 故障(优先考虑)
2. simple_bgp: 简单 BGP 网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、bgp协议故障(优先考虑)
3. ospf_enterprise: OSPF 企业网, 可能发生主机侧故障、物理链路故障、通用 frr 故障、ospf协议故障(优先考虑)
4. rip_internet: rip 小型网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、rip协议故障(优先考虑)
5. sdn_openflow: sdn 网络, 可能发生主机侧故障、物理链路故障、ovs或ryu故障(优先考虑)
6. p4_star: P4 星型网络, 可能发生主机侧故障、物理链路故障、p4-bmv2故障(优先考虑)

【根本原因说明】
你必须且仅能从以下 3 大类中选择一个最符合的英文字符串作为最终诊断结果提交。请仔细区分故障发生的载体（是主机配置出错，还是中间的路由器/交换机出错）：

1. 主机侧故障 (Host Faults) - 仅限端主机(Host)自身的配置问题：
  - ip_misconfig: 主机网卡 IP 地址或子网掩码配置错误、甚至未配置
  - default_route_missing: 主机自身的路由表中缺少默认网关路由(default via)
  - arp_poisoning: 主机自身的 ARP 缓存表被投毒，网关 MAC 地址被恶意篡改
  - interface_down: 主机的物理或逻辑网络接口处于 DOWN 状态
  - dns_error: 主机的 DNS 服务器配置错误，导致无法解析域名
  - high_cpu_load: 主机 CPU 占用率极高（如满载），导致发包或处理极慢

2. 核心网络服务故障 (Service Faults) - 发生在中间节点(Router/Switch)上的路由协议或数据面问题：
(1) 通用 frr 故障:
  - route_missing: 路由器(Router)的全局路由表中丢失了去往目标网段的路由
  - static_route_blackhole: 路由器上被人为配置了去往目标网段的黑洞路由 (blackhole)
  - router_data_plane_drop: 路由器的防火墙或 iptables 规则 (FORWARD链) 强行 DROP/REJECT 了转发流量
(2) bgp协议故障(仅针对 simple_bgp 场景):
  - bgp_neighbor_shutdown: 路由器的 BGP 邻居关系被断开/关闭 (Active/Idle状态)
  - bgp_withdraw_route: BGP 路由撤销，导致 BGP 表中无目标路由
  - bgp_wrong_peer_asn: BGP 邻居的 AS 号配置错误导致无法建联
(3) ospf协议故障(仅针对 ospf_enterprise 场景):
  - ospf_passive_interface: 路由器的接口被设置为 OSPF 被动接口，停止发送 Hello 包
  - ospf_cost_spike: OSPF 接口的开销 (Cost) 被恶意调得极高，导致流量绕路或中断
  - ospf_daemon_crash: 路由器的 OSPF 进程崩溃退出
(4) rip协议故障(仅针对 rip_internet 场景):
  - rip_passive_interface: 路由器的接口被设置为 RIP 被动接口，停止发送更新
  - rip_route_filter: 路由器被恶意配置了 distribute-list 规则，强行过滤了路由发布
  - rip_metric_offset: 路由器被恶意配置了 offset-list，大幅篡改路由跳数导致不可达
(5) ovs或ryu故障(仅针对 sdn_openflow 场景):
  - sdn_controller_crash: SDN 控制器(Ryu)宕机或断开连接
  - ovs_disconnect_controller: OpenvSwitch 与 SDN 控制器断开连接
  - ovs_global_drop_flow: OpenvSwitch 被下发了全局 Drop 所有流表
(6) p4-bmv2故障(仅针对 p4_star 场景):
  - bmv2_process_crash: P4 Bmv2 交换机进程崩溃
  - p4_table_drop: P4 交换机匹配到丢弃流表项
  - p4_wrong_forwarding: P4 交换机转发逻辑或端口映射错误

3. 物理链路故障 (Link Faults) - 连接各节点之间的网线/通道质量恶化：
  - link_latency: 链路上被人为注入了异常高且稳定的延迟
  - link_loss: 链路存在明显的报文丢包率 (Packet Loss > 0%)
  - link_jitter: 链路延迟极不稳定，出现严重抖动 (Jitter/mdev 很大)
  - link_bandwidth: 链路可用带宽被严格限制 (如 TBF 限速)，导致大流量严重拥堵

【严禁行为】
- ⚠️ 得出最终的故障结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_diagnosis` 工具并传入根本原因，只有这样系统才能接收到你的答案！
- 遇到信息不足时，务必先通过工具查询状态，绝不可随意猜测
- 次数很多，切不可仅用一个工具就下定论！
- 切勿一次性调用大量不相关的工具，应按照逻辑链条一步一步排查
- 所有工具输出结果都是稳定正确的，同样的工具+同样的输入参数切勿调用两次以上！

======================================================================
2026-03-16 02:30:39 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:30:39 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:30:43 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 无法 Ping 通 192.168.4.2 的问题。这是一个 static_routing 场景，涉及跨网段通信。

首先，让我从 h1 向目标 IP 进行 Ping 测试，确认故障现象。
2026-03-16 02:30:43 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.4.2'}
2026-03-16 02:30:56 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.4.2 (192.168.4.2) 56(84) bytes of data.

--- 192.168.4.2 ping statistics ---
10 packets transmitted, 0 received, 100% packet loss, time 9216ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:02 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
确认了，h1 到 192.168.4.2 的 Ping 测试 100% 丢包，网络完全不可达。

这是一个跨网段通信问题（h1 在 192.168.1.0/24 网段，目标 192.168.4.2 在 192.168.4.0/24 网段）。我需要逐步排查：

1. 首先检查 h1 自身的配置（IP、默认路由等）
2. 然后检查中间路由器的路由表
3. 检查是否有防火墙规则阻止流量

让我先检查 h1 的 IP 配置是否正确：
2026-03-16 02:31:02 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_ip_misconfig'
   📥 输入参数: {'host': 'h1', 'iface': 'tos1_1'}
2026-03-16 02:31:03 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_ip_misconfig)
   📤 结果详情:
3: tos1_1@if7: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 2a:49:cc:9b:f4:2a brd ff:ff:ff:ff:ff:ff link-netnsid 1
    inet 192.168.1.2/24 brd 192.168.1.255 scope global tos1_1
       valid_lft forever preferred_lft forever
    inet6 fe80::2849:ccff:fe9b:f42a/64 scope link 
       valid_lft forever preferred_lft forever
[专家提示] 请核对上述输出的IPv4地址 192.168.1.2/24 是否与【网络拓扑信息】中 h1 的接口 IP 一致，若不一致，调用 submit_diagnosis 提交 ip_misconfig。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:06 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的 IP 配置正确（192.168.1.2/24），与拓扑信息一致。

接下来检查 h1 的默认路由是否存在：
2026-03-16 02:31:06 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_default_route_missing'
   📥 输入参数: {'host': 'h1'}
2026-03-16 02:31:06 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_default_route_missing)
   📤 结果详情:
default via 192.168.1.1 dev tos1_1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.2
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:10 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 的默认路由存在，指向 192.168.1.1（r1 的接口），配置正确。

现在让我检查 h1 能否 Ping 通它的网关 192.168.1.1，确认本地链路是否正常：
2026-03-16 02:31:10 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.1.1'}
2026-03-16 02:31:20 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.
64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=0.407 ms
64 bytes from 192.168.1.1: icmp_seq=2 ttl=64 time=0.064 ms
64 bytes from 192.168.1.1: icmp_seq=3 ttl=64 time=0.050 ms
64 bytes from 192.168.1.1: icmp_seq=4 ttl=64 time=0.059 ms
64 bytes from 192.168.1.1: icmp_seq=5 ttl=64 time=0.059 ms
64 bytes from 192.168.1.1: icmp_seq=6 ttl=64 time=0.059 ms
64 bytes from 192.168.1.1: icmp_seq=7 ttl=64 time=0.075 ms
64 bytes from 192.168.1.1: icmp_seq=8 ttl=64 time=0.062 ms
64 bytes from 192.168.1.1: icmp_seq=9 ttl=64 time=0.061 ms
64 bytes from 192.168.1.1: icmp_seq=10 ttl=64 time=0.067 ms

--- 192.168.1.1 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 9218ms
rtt min/avg/max/mdev = 0.050/0.096/0.407/0.104 ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:25 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 到网关 192.168.1.1 的连通性正常。问题可能出在路由器 r1 或 r2 上，或者中间链路。

让我检查 r1 的路由表，看看是否有去往 192.168.4.0/24 网段的路由：
2026-03-16 02:31:25 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r1', 'target_ip': '192.168.4.2'}
2026-03-16 02:31:26 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor2_1 proto kernel scope link src 192.168.0.1 
192.168.1.0/24 dev tos1_1 proto kernel scope link src 192.168.1.1 
192.168.2.0/24 dev tos2_1 proto kernel scope link src 192.168.2.1 
192.168.3.0/24 via 192.168.0.2 dev tor2_1 
192.168.4.0/24 via 192.168.0.2 dev tor2_1

【内核路由匹配测试 (ip route get 192.168.4.2)】:
192.168.4.2 via 192.168.0.2 dev tor2_1 src 192.168.0.1 uid 0 
    cache

[专家提示] 内核成功匹配到了去往 192.168.4.2 的正向路由。
[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:32 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
r1 的路由表显示有去往 192.168.4.0/24 的路由，通过 192.168.0.2（r2）转发。正向路由正常。

根据专家提示，如果正向路由正常但 Ping 仍 100% 丢包，可能是回程路由缺失。让我检查 r2 的路由表，看看是否有去往 192.168.1.0/24（h1 所在网段）的回程路由：
2026-03-16 02:31:32 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_routing_table'
   📥 输入参数: {'router': 'r2', 'target_ip': '192.168.1.2'}
2026-03-16 02:31:33 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_routing_table)
   📤 结果详情:
【全局路由表 (ip route show)】:
192.168.0.0/24 dev tor1_1 proto kernel scope link src 192.168.0.2 
192.168.1.0/24 via 192.168.0.1 dev tor1_1 
192.168.2.0/24 via 192.168.0.1 dev tor1_1 
192.168.3.0/24 dev tos3_1 proto kernel scope link src 192.168.3.1 
192.168.4.0/24 dev tos4_1 proto kernel scope link src 192.168.4.1

【内核路由匹配测试 (ip route get 192.168.1.2)】:
192.168.1.2 via 192.168.0.1 dev tor1_1 src 192.168.0.2 uid 0 
    cache

[专家提示] 内核成功匹配到了去往 192.168.1.2 的正向路由。
[专家提示] 若正向路由正常但 Ping 仍 100% 丢包，极大概率是【回程路由缺失】(对端路由器缺少去往源 IP 的路由)。请务必再次调用本工具检查对端路由器的回程路由。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:37 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
r2 的路由表也显示有去往 192.168.1.0/24 的回程路由，通过 192.168.0.1（r1）转发。回程路由也正常。

既然路由都正常，问题可能出在数据面防火墙规则上。让我检查 r1 和 r2 是否有 iptables 规则阻止了流量：
2026-03-16 02:31:37 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_data_plane_drop'
   📥 输入参数: {'router': 'r1'}
2026-03-16 02:31:38 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_data_plane_drop)
   📤 结果详情:
Chain FORWARD (policy ACCEPT)
target     prot opt source               destination         
DROP       icmp --  0.0.0.0/0            0.0.0.0/0
[系统警告] 发现路由器的 FORWARD 数据面中存在恶意的 DROP 或 REJECT 拦截规则，立即调用 `submit_diagnosis` 提交 router_data_plane_drop。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:31:42 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
找到了！r1 的 FORWARD 链中有一个 DROP icmp 的规则，这会阻止所有 ICMP 流量（包括 Ping）通过 r1 转发。

这就是导致 h1 无法 Ping 通 192.168.4.2 的根本原因：路由器 r1 的防火墙规则强制 DROP 了 ICMP 流量。

根据根本原因说明，这属于"router_data_plane_drop"（路由器的防火墙或 iptables 规则强行 DROP/REJECT 了转发流量）。
2026-03-16 02:31:42 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'router_data_plane_drop'}
2026-03-16 02:31:42 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: router_data_plane_drop
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:31:44 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。根本原因是 r1 路由器的 FORWARD 链中存在 DROP icmp 的防火墙规则，导致所有 ICMP 流量被丢弃，因此 h1 无法 Ping 通 192.168.4.2。
2026-03-16 02:31:44 [INFO] SystemLogger: Agent Diagnosis Finished. Result: router_data_plane_drop

📊 [测试结果评估]
预期 Root Cause: router_data_plane_drop
Agent 诊断结论: router_data_plane_drop
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (static_routing)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


======================================================================
🎉 [自动化测试套件执行完毕]
⏱️  总耗时: 7 分 36 秒
请向上翻阅日志查看每一个用例的具体 Agent 诊断过程和 ✅❌ 结果。
======================================================================