======================================================================
🧪 [开始自动化测试套件]: 链路类故障 (Link Faults)
📍 测试场景: simple_bgp
📝 包含用例: 4 个
======================================================================


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 1/4]: inject_link_latency
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_link_latency] -> 预期: [link_latency]
==================================================
[System] 🛠️  正在部署网络拓扑 (simple_bgp via simple_bgp.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:08:25 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:08:25 [INFO] SystemLogger: Injecting fault: inject_link_latency ...

[Inject Pool] 正在为 simple_bgp 下发 LINK 故障: inject_link_latency
2026-03-16 02:08:25 [INFO] SystemLogger: 正在注入故障: h1 链路 l3 增加延迟 500ms (抖动 0ms)
{'code': 1, 'msg': '链路配置成功'}
2026-03-16 02:08:28 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 simple_bgp 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tor1_1(192.168.2.2) | 默认网关: 192.168.2.1
- h2 [host] | 接口: tor2_1(192.168.3.2) | 默认网关: 192.168.3.1
- h3 [host] | 接口: tor2_1(192.168.4.2) | 默认网关: 192.168.4.1
- h4 [host] | 接口: tor3_1(192.168.5.2) | 默认网关: 192.168.5.1
- r1 [router] | 接口: toh1_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: toh2_1(192.168.3.1), tor1_1(192.168.0.2), toh3_1(192.168.4.1), tor3_1(192.168.1.1)
- r3 [router] | 接口: toh4_1(192.168.5.1), tor2_1(192.168.1.2)

[链路]
- 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
- 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
- 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
- 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
- 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

【当前故障】
用户投诉: 主机 h1 访问 h2 时，链路出现严重网络卡顿、延迟极高或丢包等现象。

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
2026-03-16 02:08:28 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:08:28 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:08:40 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 访问 h2 时出现的网络卡顿、延迟极高或丢包问题。

首先，让我从 h1 向 h2 进行 Ping 测试，观察当前的连通性状态和延迟情况。
2026-03-16 02:08:40 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.3.2'}
2026-03-16 02:08:50 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.3.2 (192.168.3.2) 56(84) bytes of data.
64 bytes from 192.168.3.2: icmp_seq=1 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=2 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=3 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=4 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=5 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=6 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=7 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=8 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=9 ttl=62 time=500 ms
64 bytes from 192.168.3.2: icmp_seq=10 ttl=62 time=500 ms

--- 192.168.3.2 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 9006ms
rtt min/avg/max/mdev = 500.084/500.104/500.169/0.707 ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:09:04 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
Ping 测试显示：
- 0% 丢包，但延迟非常高（约 500ms）
- 延迟非常稳定（mdev 只有 0.707ms），说明不是抖动问题

根据专家经验，当用户投诉"网络卡顿、慢"但 Ping 测试是 0% 丢包且低延迟时，需要检查链路质量或 CPU 占用。但这里延迟确实很高（500ms），所以可能是链路被注入了延迟。

让我先检查 h1 到目标 IP 的链路质量，看看是否有延迟注入：
2026-03-16 02:09:04 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_link_quality'
   📥 输入参数: {'host': 'h1', 'target_ip': '192.168.3.2'}
2026-03-16 02:09:14 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_link_quality)
   📤 结果详情:
qdisc noqueue 0: dev lo root refcnt 2 
qdisc noqueue 0: dev eth0 root refcnt 2 
qdisc tbf 5: dev tor1_1 root refcnt 2 rate 10Mbit burst 10Kb lat 71.8ms 
qdisc netem 10: dev tor1_1 parent 5: limit 2000000 delay 500.0ms
[专家提示] 检测到 Ping 延迟极高但很稳定 (平均延迟 avg = 500.105 ms, 抖动 mdev = 0.447 ms)。
🎯 确诊：被注入了高延迟故障！请直接调用 submit_diagnosis 提交 link_latency。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:09:20 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
工具输出明确显示：
- 在 h1 的 tor1_1 接口上，有 netem 规则注入了 500.0ms 的延迟（`delay 500.0ms`）
- 专家提示也明确指出这是被注入了高延迟故障

这解释了为什么 Ping 测试显示 500ms 的稳定延迟。根本原因是链路上被人为注入了延迟。

根据根本原因说明，这属于物理链路故障中的 `link_latency`（链路上被人为注入了异常高且稳定的延迟）。
2026-03-16 02:09:20 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'link_latency'}
2026-03-16 02:09:20 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: link_latency
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:09:23 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障原因是 `link_latency` - 在 h1 的 tor1_1 接口上被人为注入了 500ms 的延迟，导致 h1 访问 h2 时出现极高的网络延迟。
2026-03-16 02:09:23 [INFO] SystemLogger: Agent Diagnosis Finished. Result: link_latency

📊 [测试结果评估]
预期 Root Cause: link_latency
Agent 诊断结论: link_latency
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (simple_bgp)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 2/4]: inject_link_loss
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_link_loss] -> 预期: [link_loss]
==================================================
[System] 🛠️  正在部署网络拓扑 (simple_bgp via simple_bgp.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:10:49 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:10:49 [INFO] SystemLogger: Injecting fault: inject_link_loss ...

[Inject Pool] 正在为 simple_bgp 下发 LINK 故障: inject_link_loss
2026-03-16 02:10:49 [INFO] SystemLogger: 正在注入故障: h1 链路 l3 丢包率 50%
{'code': 1, 'msg': '链路配置成功'}
2026-03-16 02:10:52 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 simple_bgp 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tor1_1(192.168.2.2) | 默认网关: 192.168.2.1
- h2 [host] | 接口: tor2_1(192.168.3.2) | 默认网关: 192.168.3.1
- h3 [host] | 接口: tor2_1(192.168.4.2) | 默认网关: 192.168.4.1
- h4 [host] | 接口: tor3_1(192.168.5.2) | 默认网关: 192.168.5.1
- r1 [router] | 接口: toh1_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: toh2_1(192.168.3.1), tor1_1(192.168.0.2), toh3_1(192.168.4.1), tor3_1(192.168.1.1)
- r3 [router] | 接口: toh4_1(192.168.5.1), tor2_1(192.168.1.2)

[链路]
- 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
- 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
- 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
- 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
- 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

【当前故障】
用户投诉: 主机 h1 访问 h2 时，链路出现严重网络卡顿、延迟极高或丢包等现象。

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
2026-03-16 02:10:52 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:10:52 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:11:01 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 访问 h2 时出现的网络卡顿、延迟极高或丢包问题。

首先，让我从 h1 向 h2 进行 Ping 测试，观察实际的连通性和延迟情况。
2026-03-16 02:11:01 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.3.2'}
2026-03-16 02:11:12 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.3.2 (192.168.3.2) 56(84) bytes of data.
64 bytes from 192.168.3.2: icmp_seq=1 ttl=62 time=0.127 ms
64 bytes from 192.168.3.2: icmp_seq=2 ttl=62 time=0.080 ms
64 bytes from 192.168.3.2: icmp_seq=6 ttl=62 time=0.076 ms
64 bytes from 192.168.3.2: icmp_seq=9 ttl=62 time=0.089 ms
64 bytes from 192.168.3.2: icmp_seq=10 ttl=62 time=0.082 ms

--- 192.168.3.2 ping statistics ---
10 packets transmitted, 5 received, 50% packet loss, time 9200ms
rtt min/avg/max/mdev = 0.076/0.090/0.127/0.022 ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:11:17 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
Ping 测试显示有 50% 的丢包率，这说明确实存在网络问题。延迟看起来很低（约 0.1ms），但丢包率很高。

根据专家经验，当用户投诉"网络卡顿、慢"或"不稳定"时，即使 Ping 测试显示低延迟，也需要检查链路质量或 CPU 占用。这里确实有 50% 丢包，说明问题真实存在。

让我先检查 h1 到 h2 的链路质量，看看是否有链路层面的问题（如丢包、延迟注入等）。
2026-03-16 02:11:17 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_link_quality'
   📥 输入参数: {'host': 'h1', 'target_ip': '192.168.3.2'}
2026-03-16 02:11:29 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_link_quality)
   📤 结果详情:
qdisc noqueue 0: dev lo root refcnt 2 
qdisc noqueue 0: dev eth0 root refcnt 2 
qdisc tbf 5: dev tor1_1 root refcnt 2 rate 10Mbit burst 10Kb lat 71.8ms 
qdisc netem 10: dev tor1_1 parent 5: limit 2000000 loss 50%
[专家提示] 检测到丢包率为 50.0% > 0%。
🎯 确诊：被注入了丢包故障！请直接调用 submit_diagnosis 提交 link_loss。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:11:33 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
工具输出明确显示在 h1 的 tor1_1 接口上配置了 netem 规则，注入了 50% 的丢包率（loss 50%）。这直接解释了为什么 Ping 测试有 50% 的丢包。

根据专家提示，已经确诊是被注入了丢包故障，根本原因是链路丢包（link_loss）。

让我提交诊断结果：
2026-03-16 02:11:33 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'link_loss'}
2026-03-16 02:11:33 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: link_loss
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:11:36 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障根本原因是链路丢包（link_loss）。

**故障总结：**
- 用户投诉 h1 访问 h2 时网络卡顿、延迟高或丢包
- Ping 测试显示 50% 丢包率
- 检查 h1 的链路质量发现，在 tor1_1 接口上配置了 netem 规则，人为注入了 50% 的丢包率（loss 50%）
- 根本原因：link_loss（链路丢包）
2026-03-16 02:11:36 [INFO] SystemLogger: Agent Diagnosis Finished. Result: link_loss

📊 [测试结果评估]
预期 Root Cause: link_loss
Agent 诊断结论: link_loss
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (simple_bgp)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 3/4]: inject_link_jitter
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_link_jitter] -> 预期: [link_jitter]
==================================================
[System] 🛠️  正在部署网络拓扑 (simple_bgp via simple_bgp.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:13:04 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:13:04 [INFO] SystemLogger: Injecting fault: inject_link_jitter ...

[Inject Pool] 正在为 simple_bgp 下发 LINK 故障: inject_link_jitter
2026-03-16 02:13:04 [INFO] SystemLogger: 正在注入故障: h1 链路 l3 高抖动 80ms
{'code': 1, 'msg': '链路配置成功'}
2026-03-16 02:13:06 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 simple_bgp 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tor1_1(192.168.2.2) | 默认网关: 192.168.2.1
- h2 [host] | 接口: tor2_1(192.168.3.2) | 默认网关: 192.168.3.1
- h3 [host] | 接口: tor2_1(192.168.4.2) | 默认网关: 192.168.4.1
- h4 [host] | 接口: tor3_1(192.168.5.2) | 默认网关: 192.168.5.1
- r1 [router] | 接口: toh1_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: toh2_1(192.168.3.1), tor1_1(192.168.0.2), toh3_1(192.168.4.1), tor3_1(192.168.1.1)
- r3 [router] | 接口: toh4_1(192.168.5.1), tor2_1(192.168.1.2)

[链路]
- 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
- 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
- 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
- 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
- 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

【当前故障】
用户投诉: 主机 h1 访问 h2 时，链路出现严重网络卡顿、延迟极高或丢包等现象。

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
2026-03-16 02:13:06 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:13:06 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:13:17 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 访问 h2 时出现的网络卡顿、延迟极高或丢包问题。

首先，让我从 h1 向 h2 进行 Ping 测试，观察当前的连通性状态和延迟情况。
2026-03-16 02:13:17 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.3.2'}
2026-03-16 02:13:27 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.3.2 (192.168.3.2) 56(84) bytes of data.
64 bytes from 192.168.3.2: icmp_seq=1 ttl=62 time=153 ms
64 bytes from 192.168.3.2: icmp_seq=2 ttl=62 time=28.7 ms
64 bytes from 192.168.3.2: icmp_seq=3 ttl=62 time=116 ms
64 bytes from 192.168.3.2: icmp_seq=4 ttl=62 time=0.088 ms
64 bytes from 192.168.3.2: icmp_seq=5 ttl=62 time=74.7 ms
64 bytes from 192.168.3.2: icmp_seq=6 ttl=62 time=120 ms
64 bytes from 192.168.3.2: icmp_seq=7 ttl=62 time=69.7 ms
64 bytes from 192.168.3.2: icmp_seq=8 ttl=62 time=117 ms
64 bytes from 192.168.3.2: icmp_seq=9 ttl=62 time=0.063 ms
64 bytes from 192.168.3.2: icmp_seq=10 ttl=62 time=148 ms

--- 192.168.3.2 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 9028ms
rtt min/avg/max/mdev = 0.063/83.025/153.214/54.700 ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:13:35 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
Ping 测试显示：
- 0% 丢包，但延迟非常高且不稳定
- 延迟范围从 0.063ms 到 153ms，平均 83ms，抖动 (mdev) 高达 54.7ms

这符合用户描述的"网络卡顿、延迟极高"现象。虽然 Ping 没有丢包，但延迟波动很大，说明链路可能存在质量问题。

根据专家经验，当 Ping 显示 0% 丢包但延迟异常时，需要检查链路质量（是否有注入延迟、抖动或带宽限制）或 CPU 占用情况。

让我先检查 h1 到目标 IP 的链路质量：
2026-03-16 02:13:35 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_link_quality'
   📥 输入参数: {'host': 'h1', 'target_ip': '192.168.3.2'}
2026-03-16 02:13:45 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_link_quality)
   📤 结果详情:
qdisc noqueue 0: dev lo root refcnt 2 
qdisc noqueue 0: dev eth0 root refcnt 2 
qdisc tbf 5: dev tor1_1 root refcnt 2 rate 10Mbit burst 10Kb lat 71.8ms 
qdisc netem 10: dev tor1_1 parent 5: limit 2000000 delay 100.0ms  80.0ms
[专家提示] 检测到 Ping 延迟极度不稳定 (平均偏差 mdev = 55.317 ms)。
🎯 确诊：被注入了抖动故障！请直接调用 submit_diagnosis 提交 link_jitter。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:13:53 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
工具输出明确显示：
1. h1 的 tor1_1 接口上配置了 TBF 限速（rate 10Mbit）和 netem 延迟注入（delay 100.0ms 80.0ms）
2. 专家提示明确指出检测到 Ping 延迟极度不稳定，确诊为被注入了抖动故障

链路质量检查显示在 h1 的 tor1_1 接口上存在 netem 配置，注入了 100ms 延迟和 80ms 的抖动（delay 100.0ms 80.0ms），这导致了 Ping 测试中观察到的严重延迟波动。

根据根本原因说明，这种情况属于物理链路故障中的 `link_jitter`（链路延迟极不稳定，出现严重抖动）。

让我提交诊断结果：
2026-03-16 02:13:53 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'link_jitter'}
2026-03-16 02:13:53 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: link_jitter
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:13:59 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障根本原因是 `link_jitter`（链路抖动）。

**故障总结：**
- 用户投诉 h1 访问 h2 时网络卡顿、延迟极高
- Ping 测试显示 0% 丢包但延迟波动极大（0.063ms - 153ms，平均 83ms，抖动 54.7ms）
- 链路质量检查发现 h1 的 tor1_1 接口上配置了 netem 规则，注入了 100ms 延迟和 80ms 抖动
- 这导致数据包在传输过程中出现严重的延迟不稳定，符合 `link_jitter` 故障特征
2026-03-16 02:13:59 [INFO] SystemLogger: Agent Diagnosis Finished. Result: link_jitter

📊 [测试结果评估]
预期 Root Cause: link_jitter
Agent 诊断结论: link_jitter
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (simple_bgp)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
▶️  [执行用例 4/4]: inject_link_bandwidth
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

==================================================
🚀 测试用例: [inject_link_bandwidth] -> 预期: [link_bandwidth]
==================================================
[System] 🛠️  正在部署网络拓扑 (simple_bgp via simple_bgp.py)...
[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...
2026-03-16 02:15:27 [INFO] SystemLogger: Fetching and simplifying topology...
2026-03-16 02:15:27 [INFO] SystemLogger: Injecting fault: inject_link_bandwidth ...

[Inject Pool] 正在为 simple_bgp 下发 LINK 故障: inject_link_bandwidth
2026-03-16 02:15:27 [INFO] SystemLogger: 正在注入故障: h1 链路 l3 限制带宽 1000kbps
{'code': 1, 'msg': '链路配置成功'}
2026-03-16 02:15:29 [INFO] SystemLogger: 
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
你是一名专业的网络故障诊断专家。

【当前网络场景】

 simple_bgp 的拓扑信息:

[节点列表]
- h1 [host] | 接口: tor1_1(192.168.2.2) | 默认网关: 192.168.2.1
- h2 [host] | 接口: tor2_1(192.168.3.2) | 默认网关: 192.168.3.1
- h3 [host] | 接口: tor2_1(192.168.4.2) | 默认网关: 192.168.4.1
- h4 [host] | 接口: tor3_1(192.168.5.2) | 默认网关: 192.168.5.1
- r1 [router] | 接口: toh1_1(192.168.2.1), tor2_1(192.168.0.1)
- r2 [router] | 接口: toh2_1(192.168.3.1), tor1_1(192.168.0.2), toh3_1(192.168.4.1), tor3_1(192.168.1.1)
- r3 [router] | 接口: toh4_1(192.168.5.1), tor2_1(192.168.1.2)

[链路]
- 链路 l3: r1(192.168.2.1) <---> h1(192.168.2.2)
- 链路 l4: r2(192.168.3.1) <---> h2(192.168.3.2)
- 链路 l5: r2(192.168.4.1) <---> h3(192.168.4.2)
- 链路 l6: r3(192.168.5.1) <---> h4(192.168.5.2)
- 链路 link_r1_r2: r1(192.168.0.1) <---> r2(192.168.0.2)
- 链路 link_r2_r3: r2(192.168.1.1) <---> r3(192.168.1.2)

【当前故障】
用户投诉: 主机 h1 访问 h2 时，链路出现严重网络卡顿、延迟极高或丢包等现象。

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
2026-03-16 02:15:29 [INFO] SystemLogger: Agent starting diagnosis task... (Max Steps: 50)
2026-03-16 02:15:29 [INFO] SystemLogger: Loading tools from all MCP Servers... (Please wait)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:15:42 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
我需要诊断 h1 访问 h2 时出现的网络卡顿、延迟极高或丢包问题。

首先，让我从 h1 向 h2 进行 Ping 测试，观察当前的连通性状态和延迟情况。
2026-03-16 02:15:42 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'ping_by_ip'
   📥 输入参数: {'src_node': 'h1', 'dst_ip': '192.168.3.2'}
2026-03-16 02:15:52 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: ping_by_ip)
   📤 结果详情:
PING 192.168.3.2 (192.168.3.2) 56(84) bytes of data.
64 bytes from 192.168.3.2: icmp_seq=1 ttl=62 time=0.134 ms
64 bytes from 192.168.3.2: icmp_seq=2 ttl=62 time=0.091 ms
64 bytes from 192.168.3.2: icmp_seq=3 ttl=62 time=0.086 ms
64 bytes from 192.168.3.2: icmp_seq=4 ttl=62 time=0.090 ms
64 bytes from 192.168.3.2: icmp_seq=5 ttl=62 time=0.083 ms
64 bytes from 192.168.3.2: icmp_seq=6 ttl=62 time=0.088 ms
64 bytes from 192.168.3.2: icmp_seq=7 ttl=62 time=0.083 ms
64 bytes from 192.168.3.2: icmp_seq=8 ttl=62 time=0.095 ms
64 bytes from 192.168.3.2: icmp_seq=9 ttl=62 time=0.081 ms
64 bytes from 192.168.3.2: icmp_seq=10 ttl=62 time=0.091 ms

--- 192.168.3.2 ping statistics ---
10 packets transmitted, 10 received, 0% packet loss, time 9192ms
rtt min/avg/max/mdev = 0.081/0.092/0.134/0.015 ms
──────────────────────────────────────────────────────────────────────
2026-03-16 02:15:57 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
Ping 测试显示 0% 丢包，延迟也很低（约 0.09ms）。但用户投诉说网络卡顿、延迟极高或丢包。根据专家经验中的"防Ping陷阱"提示：如果 Ping 测试是 0% 丢包且低延迟，但用户投诉网络卡顿，必须检查主机 CPU 占用或链路带宽限制规则。

让我先检查 h1 和 h2 的 CPU 占用情况，看看是否有高 CPU 负载导致的问题。
2026-03-16 02:15:57 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_cpu_overload'
   📥 输入参数: {'host': 'h1'}
2026-03-16 02:15:58 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_cpu_overload)
   📤 结果详情:
[WARN] h1 命令 'sh -c 'ps aux | grep [d]d'' 无输出。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:16:00 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h1 没有高 CPU 负载的异常进程。让我检查 h2 的 CPU 占用情况。
2026-03-16 02:16:00 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_cpu_overload'
   📥 输入参数: {'host': 'h2'}
2026-03-16 02:16:00 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_cpu_overload)
   📤 结果详情:
[WARN] h2 命令 'sh -c 'ps aux | grep [d]d'' 无输出。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:16:04 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
h2 也没有高 CPU 负载。既然 Ping 测试正常但用户投诉卡顿，根据专家经验，应该检查链路质量，看看是否有带宽限制或其他链路问题。

让我检查 h1 到 h2 的链路质量，看看是否有带宽限制、延迟注入或丢包等问题。
2026-03-16 02:16:04 [INFO] SystemLogger: 
🛠️  [Action / 调用工具]: 决定执行 'check_link_quality'
   📥 输入参数: {'host': 'h1', 'target_ip': '192.168.3.2'}
2026-03-16 02:16:14 [INFO] SystemLogger: 
👁️  [Observation / 工具执行返回]: (来源: check_link_quality)
   📤 结果详情:
qdisc noqueue 0: dev lo root refcnt 2 
qdisc noqueue 0: dev eth0 root refcnt 2 
qdisc tbf 5: dev tor1_1 root refcnt 2 rate 1Mbit burst 1Kb lat 791.8ms 
qdisc netem 10: dev tor1_1 parent 5: limit 2000000
[专家提示] 检测到带宽很小 (速度 rate = 1Mbit)。
🎯 确诊：被注入了限制带宽故障！请直接调用 submit_diagnosis 提交 link_bandwidth。
──────────────────────────────────────────────────────────────────────
2026-03-16 02:16:18 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
找到了根本原因！在 h1 的 tor1_1 接口上检测到了 TBF（Token Bucket Filter）带宽限制规则，rate 被限制为 1Mbit，这会导致大流量时严重拥堵，造成网络卡顿现象。

根据工具返回的专家提示，这是 link_bandwidth 故障。我需要提交这个诊断结果。
2026-03-16 02:16:18 [INFO] SystemLogger: 
🎯 [Action / 提交结论]: 调用工具 'submit_diagnosis'
   📥 提交参数: {'root_cause': 'link_bandwidth'}
2026-03-16 02:16:18 [INFO] SystemLogger: 
🎉 [Observation / 诊断结束]:
   ✅ [DIAGNOSIS_COMPLETED]: link_bandwidth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-03-16 02:16:20 [INFO] SystemLogger: 
🤔 [Thought / 逻辑推理]:
诊断完成。故障原因是链路带宽被限制（link_bandwidth）。在 h1 的 tor1_1 接口上配置了 TBF 流量整形规则，将带宽限制为 1Mbit，这导致大流量传输时出现严重拥堵，造成用户投诉的网络卡顿现象。
2026-03-16 02:16:20 [INFO] SystemLogger: Agent Diagnosis Finished. Result: link_bandwidth

📊 [测试结果评估]
预期 Root Cause: link_bandwidth
Agent 诊断结论: link_bandwidth
✅ 测试通过 (PASS)
[System] 🧹 正在销毁网络拓扑 (simple_bgp)...
[System] ✅ 拓扑销毁成功。

⏳ 缓冲 3 秒，准备进入下一个用例...


======================================================================
🎉 [自动化测试套件执行完毕]
⏱️  总耗时: 9 分 23 秒
请向上翻阅日志查看每一个用例的具体 Agent 诊断过程和 ✅❌ 结果。
======================================================================