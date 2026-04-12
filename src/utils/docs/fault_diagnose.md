# link_loss (ubuntu 主机) | 全部场景
- 典型现象：
  - 用户感知“卡顿/掉线/时通时不通”，SSH/HTTP 连接偶发中断或重传明显。
  - `ping` 有丢包（0% < loss < 100%），RTT 可能也随之波动。
  - 业务层表现为：请求超时偶发、吞吐下降、视频会议花屏等。
- 诊断步骤（工具/命令）：
  1. 队列规则检查：`node_execute()`
     - `node="{host_node}"`
     - `command="tc qdisc show"`
  2. 连通性与丢包验证：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 10 -W 2 {target_ip}"`
- 参数说明：
  - `{host_node}`：发生故障或被怀疑注入故障的主机（如 h1）
  - `{target_ip}`：对端可达目标 IP（同网段或跨网段均可，建议选稳定在线目标）
- 关键判据：
  - `tc qdisc show` 输出中出现 `netem` 且包含 `loss {xx}%`，并且 `ping` 丢包率明显（0%~<100%）=> 确诊链路丢包。
  - 若 `ping` 为 100% 丢包但 `tc` 无 `loss` 规则：优先排查路由缺失/黑洞/接口 down/防火墙 DROP，避免误判为丢包。

# link_latency (ubuntu 主机) | 全部场景
- 典型现象：
  - 网络“很慢但稳定”，请求都能成功但响应明显变慢。
  - `ping` 基本不丢包，但 RTT 平均值显著升高（例如 >50ms 或明显高于基线），抖动小。
  - TCP 连接建立/HTTP 首包时间变长，吞吐可能下降。
- 诊断步骤（工具/命令）：
  1. 队列规则检查：`node_execute()`
     - `node="{host_node}"`
     - `command="tc qdisc show"`
  2. RTT 验证：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 10 -W 2 {target_ip}"`
- 参数说明：
  - `{host_node}`：怀疑被注入延迟的主机
  - `{target_ip}`：对端测试 IP（建议同一条业务路径上真实对端）
- 关键判据：
  - `tc qdisc show` 存在 `netem ... delay {xx}ms`，同时 `ping` 的 `avg` RTT 稳定偏高且 `mdev` 很小 => 确诊链路延迟。
  - 若 RTT 偏高但 `mdev` 很大，且 `tc` 存在 `delay ... {jitter}` 字段，更像链路抖动而非纯延迟。

# link_jitter (ubuntu 主机) | 全部场景
- 典型现象：
  - 用户感知“忽快忽慢”，同一业务时延不稳定、偶发超时。
  - `ping` RTT 上下跳动明显，`mdev`（抖动）显著升高（如 >10ms）。
  - 实时业务（语音/视频/在线交互）质量下降明显。
- 诊断步骤（工具/命令）：
  1. 队列规则检查：`node_execute()`
     - `node="{host_node}"`
     - `command="tc qdisc show"`
  2. 抖动采样：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 10 -W 2 {target_ip}"`
- 参数说明：
  - `{host_node}`：怀疑被注入抖动的主机
  - `{target_ip}`：对端测试 IP
- 关键判据：
  - `tc qdisc show` 中存在 `netem` 且包含 `delay {base}ms {jitter}ms`（或等价格式），并且 `ping` 的 `mdev` 显著偏高 => 确诊链路抖动。
  - 若 RTT 偏高但抖动不明显（`mdev` 小），更符合链路延迟而非抖动。

# link_bandwidth (ubuntu 主机) | 全部场景
- 典型现象：
  - 大文件/镜像拉取/模型下载明显变慢，吞吐“被限速”，但 `ping` 可能仍正常。
  - 业务表现为带宽型任务耗时陡增，队列堆积导致间接时延上升。
  - 多连接并发时更明显（排队/拥塞）。
- 诊断步骤（工具/命令）：
  1. 速率限制规则检查：`node_execute()`
     - `node="{host_node}"`
     - `command="tc qdisc show"`
- 参数说明：
  - `{host_node}`：怀疑被限速的主机
- 关键判据：
  - `tc qdisc show` 输出中出现 `tbf` 且包含 `rate {xx}Kbit/Mbit` 等速率字段 => 确诊链路带宽限制。
  - 若无 `tbf` 但业务慢：再排查 CPU/内存负载、磁盘瓶颈或上游链路拥塞（非本机 tc 注入）。

---

# ip_misconfig (ubuntu 主机) | 全部场景
- 典型现象：
  - 主机“像换了 IP/丢了 IP”，同网段 ARP 也可能异常。
  - `ping` 网关/同网段主机失败或出现“Destination Host Unreachable”。
  - 仅该主机异常，其他主机互通正常。
- 诊断步骤（工具/命令）：
  1. IP 地址核对：`node_execute()`
     - `node="{host_node}"`
     - `command="ip addr show {iface}"`
  2. 基础连通性验证（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 4 -W 2 {gateway_ip}"`
- 参数说明：
  - `{host_node}`：目标主机
  - `{iface}`：连接网络的网卡名
  - `{gateway_ip}`：该网段网关 IP（或同网段可达邻居 IP）
- 关键判据：
  - `ip addr show` 中 `inet` 缺失（IP 丢失）或 `inet` 地址与拓扑预配不一致 => 确诊 IP 配置错误。
  - 若 IP 正确但仍不通：转查默认路由、ARP、接口状态、防火墙。

# default_route_missing (ubuntu 主机) | 全部场景
- 典型现象：
  - 同网段通信正常（能 ping 同网段），跨网段/访问外网全部失败。
  - `ping` 远端网段返回 `Network is unreachable` 或超时。
  - 应用表现为“内网可用、外网不可用”。
- 诊断步骤（工具/命令）：
  1. 路由表检查：`node_execute()`
     - `node="{host_node}"`
     - `command="ip route show"`
  2. 跨网段探测（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 4 -W 2 {remote_ip}"`
- 参数说明：
  - `{host_node}`：目标主机
  - `{remote_ip}`：跨网段目标 IP（确保正常情况下可达）
- 关键判据：
  - `ip route show` 中找不到 `default via ...`（或 `0.0.0.0/0`）且接口为 UP => 确诊默认路由缺失。
  - 若默认路由存在但跨网段不通：继续排查上游路由器转发/黑洞/ACL。

# arp_poisoning (ubuntu 主机) | 全部场景
- 典型现象：
  - 仅对“某个特定 IP”不通（同网段内其他主机可能正常）。
  - `ping` 特定目标超时，但 ping 网关/其他同网段主机正常。
  - 可能出现“MAC 地址突然变化”“邻居项变为 FAILED/INCOMPLETE/PERMANENT”。
- 诊断步骤（工具/命令）：
  1. ARP/邻居表检查：`node_execute()`
     - `node="{host_node}"`
     - `command="ip neigh show"`
  2. 对特定目标探测（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 4 -W 2 {target_ip}"`
- 参数说明：
  - `{host_node}`：被投毒或怀疑异常的主机
  - `{target_ip}`：出现通信异常的对端 IP
- 关键判据：
  - `ip neigh show` 中 `{target_ip}` 对应项为 `FAILED`/持续 `INCOMPLETE`，或 MAC 明显伪造（如 `aa:bb:cc:dd:ee:ff`），或出现异常静态 `PERMANENT` 绑定 => 确诊 ARP 缓存投毒。
  - 若邻居项正常但不通：排查对端防火墙/接口 down/路由问题。

# interface_down (ubuntu 主机) | 全部场景
- 典型现象：
  - 主机/服务器/客户端彻底脱网：`ping` 任意目标失败。
  - 本机看不到链路、DHCP 续租失败、ARP 无法解析。
  - 仅该主机异常，其他节点正常。
- 诊断步骤（工具/命令）：
  1. 网卡状态检查：`node_execute()`
     - `node="{host_node}"`
     - `command="ip link show {iface}"`
  2. 地址状态联动检查（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ip addr show {iface}"`
- 参数说明：
  - `{host_node}`：目标主机名称（如 h1）
  - `{iface}`：连接网络的网卡名
- 关键判据：
  - 输出包含明确 `state DOWN`（或接口 flags 显示 DOWN）=> 100% 确诊接口宕机。
  - 若接口 UP 但不通：转查 IP/路由/ARP/tc/iptables。

# dns_error (ubuntu 主机) | 全部场景
- 典型现象：
  - 能 `ping` 通 IP（如公网 IP/网关），但访问域名失败（解析失败/超时）。
  - `curl https://example.com` 报“Could not resolve host”（若环境具备 curl）。
  - 仅域名相关业务不可用，纯 IP 访问正常。
- 诊断步骤（工具/命令）：
  1. DNS 配置检查：`node_execute()`
     - `node="{host_node}"`
     - `command="cat /etc/resolv.conf"`
  2. 域名解析侧向验证（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 2 -W 2 {domain_name}"`
  3. 纯 IP 连通性对照（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 2 -W 2 {known_good_ip}"`
- 参数说明：
  - `{host_node}`：目标主机
  - `{domain_name}`：被访问的域名（如 www.example.com）
  - `{known_good_ip}`：已知可达 IP（如网关/某服务器 IP）
- 关键判据：
  - `/etc/resolv.conf` 中 `nameserver` 指向明显错误/不可达地址（如 `0.1.2.3`）=> 确诊 DNS 配置错误。
  - 若 resolv.conf 正常但解析仍失败：排查上游 DNS 服务、53 端口 ACL、网络丢包/延迟。

# cpu_overload (ubuntu 主机) | 全部场景
- 典型现象：
  - 主机整体“很卡”，SSH 交互延迟高；业务处理慢并伴随网络超时（因应用线程调度被饿死）。
  - `ping` 可能也出现 RTT 抖动或丢包（用户态/协议栈处理不及时）。
  - 同机多服务同时变慢。
- 诊断步骤（工具/命令）：
  1. 资源快照：`node_execute()`
     - `node="{host_node}"`
     - `command="top -b -n 1 | head -n 15"`
- 参数说明：
  - `{host_node}`：目标主机
- 关键判据：
  - `top` 中 CPU `id`（空闲）趋近 0，且存在 `stress-ng` 或某进程 `%CPU` 极高并长期占用 => 确诊 CPU 满载。
  - 若 CPU 不高但业务慢：排查内存、磁盘 IO、网络 tc/丢包等。

# routing_error (ubuntu 主机) | 全部场景
- 典型现象：
  - 对“特定网段”不可达，但其他网段正常（命中错误静态路由）。
  - `ping` 某远端网段超时/不可达；同网段与其他远端可能正常。
  - 路径异常：流量被送往不存在网关或错误出口。
- 诊断步骤（工具/命令）：
  1. 路由表审计：`node_execute()`
     - `node="{host_node}"`
     - `command="ip route show"`
  2. 单目的选路验证：`node_execute()`
     - `node="{host_node}"`
     - `command="ip route get {target_ip}"`
- 参数说明：
  - `{host_node}`：目标主机
  - `{target_ip}`：不可达目标网段内的一个具体 IP
- 关键判据：
  - `ip route show` 出现可疑静态路由（指向非预期 `via {wrong_gw}`），且 `ip route get` 显示流量将走该错误网关 => 确诊主机静态路由错误。
  - 若路由表正确但仍不通：排查上游路由器路由缺失/ACL/黑洞。

# mask_error (ubuntu 主机) | 全部场景
- 典型现象：
  - “同网段部分主机可达、部分不可达”，尤其是本应在同一 /24 的邻居被当成跨网段处理。
  - ARP 表项异常少（因为主机认为对端不在直连网段，不发 ARP）。
  - `ping` 某些同网段地址出现 `Destination Host Unreachable` 或走网关导致失败。
- 诊断步骤（工具/命令）：
  1. 掩码核对：`node_execute()`
     - `node="{host_node}"`
     - `command="ip addr show {iface}"`
  2. 路由与直连判断（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ip route show"`
- 参数说明：
  - `{host_node}`：目标主机
  - `{iface}`：目标网卡
- 关键判据：
  - `ip addr show` 的 `inet x.x.x.x/{cidr}` 中 CIDR 与规划明显不一致（例如应为 /24 却变成 /30）=> 确诊子网掩码错误。
  - 若掩码正确但同网段仍不通：排查 ARP 投毒/二层隔离/交换机策略。

# host_port_exhaustion (ubuntu 主机) | 全部场景
- 典型现象：
  - 应用大量报错：`Cannot assign requested address`、新连接建立失败、短连接服务大面积失败。
  - `ping` 常常仍正常（ICMP 不依赖 TCP 临时端口），但 HTTP/TCP 新建连接失败。
  - 在高并发客户端或 NAT 场景更明显。
- 诊断步骤（工具/命令）：
  1. 临时端口范围检查：`node_execute()`
     - `node="{host_node}"`
     - `command="sysctl net.ipv4.ip_local_port_range"`
- 参数说明：
  - `{host_node}`：目标主机
- 关键判据：
  - `net.ipv4.ip_local_port_range` 被设置为极窄范围（例如起止相同，仅 1 个端口）=> 确诊主机端口耗尽/端口范围被锁死。
  - 若端口范围正常但仍连接失败：排查 conntrack、应用 FD 耗尽、对端端口/ACL。

---

# route_missing (frr 路由器) | static_routing
- 典型现象：
  - 跨网段到“某个业务网段”完全不可达，源主机可能报 `Destination Net Unreachable`。
  - 同网段或其他网段仍可达（仅缺失特定前缀）。
  - traceroute（若有）可能停在某一跳；`ping` 目标网段全超时。
- 诊断步骤（工具/命令）：
  1. 路由表确认：`node_execute()`
     - `node="{router}"`
     - `command="ip route show"`
  2. 单目的路由解析：`node_execute()`
     - `node="{router}"`
     - `command="ip route get {target_ip}"`
- 参数说明：
  - `{router}`：目标路由器（如 r1/r2）
  - `{target_ip}`：缺失网段内任意主机 IP（如 192.168.4.2）
- 关键判据：
  - `ip route show` 中不存在目标 `{network}` 路由，且 `ip route get {target_ip}` 输出 `unreachable`/`Network is unreachable` => 确诊目标网段路由缺失。
  - 若路由存在但业务不通：排查转发开关、iptables FORWARD、下游链路/接口地址。

# static_route_blackhole (frr 路由器) | static_routing
- 典型现象：
  - 到某网段“有路由但永远不通”，表现为稳定丢弃（黑洞）。
  - 源主机 ping 远端网段全部超时；可能无 ICMP 不可达返回（静默丢弃）。
  - 仅影响被黑洞的前缀，其余前缀正常。
- 诊断步骤（工具/命令）：
  1. 路由表检查黑洞条目：`node_execute()`
     - `node="{router}"`
     - `command="ip route show"`
  2. 路由决策验证（可选）：`node_execute()`
     - `node="{router}"`
     - `command="ip route get {target_ip}"`
- 参数说明：
  - `{router}`：目标路由器
  - `{target_ip}`：被黑洞前缀内 IP
- 关键判据：
  - `ip route show` 明确出现 `blackhole {network}` => 直接确诊静态黑洞路由。
  - 若 `ip route get` 返回异常（如 `Invalid argument`）可作为辅证，但以路由表黑洞条目为准。

# data_plane_drop (frr 路由器) | static_routing
- 典型现象：
  - “跨网段 ping 不通，但同网段 ping 正常”，且更像被策略丢弃而非路由缺失。
  - 只影响 ICMP（如果仅 DROP icmp），TCP/UDP 业务可能仍部分正常。
  - 源主机到网关可达，但到远端主机超时。
- 诊断步骤（工具/命令）：
  1. FORWARD 链规则检查：`node_execute()`
     - `node="{router}"`
     - `command="iptables -L FORWARD -n"`
  2. 跨网段探测：`node_execute()`
     - `node="{src_host}"`
     - `command="ping -c 4 -W 2 {remote_ip}"`
  3. 同网段对照探测：`node_execute()`
     - `node="{src_host}"`
     - `command="ping -c 4 -W 2 {same_subnet_ip}"`
- 参数说明：
  - `{router}`：注入/怀疑拦截的路由器
  - `{src_host}`：业务源主机
  - `{remote_ip}`：需要经过路由器转发的目标 IP
  - `{same_subnet_ip}`：与 `{src_host}` 同网段的另一台主机 IP
- 关键判据：
  - 路由器 `iptables -L FORWARD -n` 存在 `icmp` 的 `DROP` 规则，且跨网段 ping 全超时、同网段 ping 正常 => 确诊数据面 ICMP 阻断。
  - 若 FORWARD 无规则但不通：转查 ip_forward、路由缺失/黑洞。

# frr_service_down (frr 路由器) | static_routing
- 典型现象：
  - 路由器“路由能力突然消失/无法查看 FRR 路由”，动态/静态管理面不可用。
  - `vtysh` 报错：`failed to connect to any daemons`。
  - 跨网段转发可能大面积异常（视内核路由残留而定）。
- 诊断步骤（工具/命令）：
  1. FRR 控制面连通性：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip route"'`
  2. 进程核对：`node_execute()`
     - `node="{router}"`
     - `command="ps aux"`
- 参数说明：
  - `{router}`：目标 FRR 路由器
- 关键判据：
  - `vtysh` 明确报 `failed to connect to any daemons`，且 `ps aux` 中看不到 `zebra`（关键）=> 确诊 FRR 进程宕机。
  - 若仅 `bgpd` 不在但 `zebra` 在：更像 BGP 单进程故障，不应误判为 FRR 全部宕机。

# ip_forward_disabled (frr 路由器) | static_routing
- 典型现象：
  - 路由器本机地址可达（能 ping 网关接口），但“所有经它转发的流量”失败。
  - 源主机 `ping` 路由器接口 IP 正常；`ping` 远端网段失败。
  - 类似“路由器变成只响应本机、不会转发”。
- 诊断步骤（工具/命令）：
  1. 转发开关检查：`node_execute()`
     - `node="{router}"`
     - `command="sysctl net.ipv4.ip_forward"`
  2. 跨网段探测：`node_execute()`
     - `node="{src_host}"`
     - `command="ping -c 4 -W 2 {remote_ip}"`
  3. 网关可达性对照：`node_execute()`
     - `node="{src_host}"`
     - `command="ping -c 4 -W 2 {router_ip}"`
- 参数说明：
  - `{router}`：中间转发路由器
  - `{src_host}`：源主机
  - `{remote_ip}`：需转发到达的远端 IP
  - `{router_ip}`：源主机默认网关接口 IP
- 关键判据：
  - `sysctl` 显示 `net.ipv4.ip_forward = 0`，且源主机能 ping 通 `{router_ip}` 但 ping 不通 `{remote_ip}` => 确诊路由转发关闭。
  - 若 ip_forward=1 仍不通：排查 FORWARD 链 ACL、路由缺失/黑洞。

# router_interface_ip_wrong (frr 路由器) | static_routing
- 典型现象：
  - 与该路由器直连的整个网段异常：主机无法 ARP 到网关、无法 ping 网关。
  - 现象可能像“网关 IP 消失/换了”，同网段主机间互通可能仍在。
  - 跨网段业务大面积失败（因为默认网关不可用）。
- 诊断步骤（工具/命令）：
  1. 路由器接口地址检查：`node_execute()`
     - `node="{router}"`
     - `command="ip addr show {iface}"`
  2. 直连主机验证原网关：`node_execute()`
     - `node="{host_on_lan}"`
     - `command="ping -c 4 -W 2 {original_gateway_ip}"`
- 参数说明：
  - `{router}`：目标路由器
  - `{iface}`：被怀疑篡改的路由器三层接口（如 tos1_1）
  - `{host_on_lan}`：与该接口直连的主机
  - `{original_gateway_ip}`：规划的原网关 IP（如 192.168.1.1）
- 关键判据：
  - `ip addr show` 显示接口 `inet` 已变为非规划网段地址，且直连主机无法 ping 通 `{original_gateway_ip}` => 确诊路由器接口地址错误。
  - 若接口 IP 正确但主机仍 ping 不通：排查主机自身 IP/掩码/ARP、接口 down。

---

# bgp_neighbor_shutdown (frr 路由器) | simple_bgp
- 典型现象：
  - 跨 AS/跨域流量中断或大范围绕行，部分远端前缀不可达。
  - `ping` 远端网段失败、业务访问断开；本地直连仍可能正常。
  - BGP 邻居会话不在 Established，可能被标注为管理员关闭（取决于实现输出）。
- 诊断步骤（工具/命令）：
  1. 配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 邻居状态检查：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp summary"'`
- 参数说明：
  - `{router}`：发生故障的 BGP 路由器
- 关键判据：
  - running-config 中出现 `neighbor {neighbor_ip} shutdown`，且 summary 中该邻居非 Established => 确诊管理性关闭 BGP 邻居。
  - 若配置无 shutdown 但邻居仍不起来：转查 ACL 阻断、对端 ASN 错误、链路/接口问题。

# bgp_withdraw_route (frr 路由器) | simple_bgp
- 典型现象：
  - “邻居还在，但某个前缀突然消失”：远端特定网段不可达，其他网段正常。
  - `show ip bgp summary` 显示 Established，但路由表/转发表缺少目标前缀。
  - 业务表现为只影响部分服务网段。
- 诊断步骤（工具/命令）：
  1. 邻居会话确认：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp summary"'`
  2. 配置审计是否撤销发布：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
- 参数说明：
  - `{router}`：发生撤销宣告的路由器（发布端或中间端）
- 关键判据：
  - summary 显示邻居仍 Established，同时 running-config 中目标 `network {network}` 不存在或 `redistribute connected` 被撤销 => 确诊 BGP 撤销网段宣告。
  - 若配置仍在但对端学不到：排查出方向 route-map、MED/LP 策略、过滤器或会话刷新未 clear。

# bgp_wrong_peer_asn (frr 路由器) | simple_bgp
- 典型现象：
  - BGP 邻居长期无法建立（Idle/Active 循环），跨域路由缺失导致大范围不可达。
  - 业务层表现为跨 AS 访问失败、部分网段“像断网”。
  - 即使底层 `ping` 对端接口 IP 正常，也无法建立 BGP。
- 诊断步骤（工具/命令）：
  1. 邻居 ASN 配置核对：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 邻居状态确认：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp summary"'`
- 参数说明：
  - `{router}`：BGP 配置可能错误的一端
- 关键判据：
  - running-config 中 `neighbor {neighbor_ip} remote-as {wrong_peer_asn}` 与对端真实 ASN 不一致，且 summary 中长期非 Established => 确诊对端 ASN 配置错误。
  - 若 ASN 正确但仍不建邻：排查 TCP/179 ACL、邻居 shutdown、链路丢包/延迟。

# acl_blocking_bgp_traffic (frr 路由器) | simple_bgp
- 典型现象：
  - BGP 会话断开后无法重连；跨域路由丢失导致远端不可达。
  - 底层 IP 连通可能正常（能 ping 对端接口），但 TCP 179 建连失败。
  - 业务表现为跨域服务间歇性失败或完全失败。
- 诊断步骤（工具/命令）：
  1. INPUT 链 ACL 检查：`node_execute()`
     - `node="{router}"`
     - `command="iptables -L INPUT -n"`
  2. BGP 会话状态：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp summary"'`
- 参数说明：
  - `{router}`：被注入 ACL 的路由器（任一 BGP 端）
- 关键判据：
  - `iptables -L INPUT -n` 存在 `tcp dpt:179` 的 `DROP` 规则，且 BGP summary 中邻居无法进入 Established => 确诊 ACL 阻断 BGP 流量。
  - 若无 ACL 但会话不起来：转查 remote-as、neighbor shutdown、链路问题。

# bgp_local_pref_spike (frr 路由器) | simple_bgp
- 典型现象：
  - 路由仍可达但“路径选择异常”：流量突然改走非预期入口/绕路，时延上升或链路拥塞。
  - 某些前缀的最佳路径突然变化，可能导致局部不可达（如回程不对称触发策略）。
  - 邻居会话通常仍为 Established。
- 诊断步骤（工具/命令）：
  1. 配置审计 route-map：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 会话健康检查：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp summary"'`
  3. 精确前缀属性确认：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip bgp {target_network}"'`
- 参数说明：
  - `{router}`：被注入 localpref 策略的路由器
  - `{target_network}`：受影响的目标前缀（如 192.168.2.0）
- 关键判据：
  - running-config 显示邻居入方向绑定 route-map，且包含 `set local-preference 999`（或明显高于默认 100）；
  - `show ip bgp {target_network}` 中明确出现 `localpref 999` => 确诊 Local Preference 异常升高导致选路异常。
  - 不要只看总表；必须用具体前缀命令核实属性。

# bgp_med_spike (frr 路由器) | simple_bgp
- 典型现象：
  - 对端更偏好其他入口：入站流量切换/绕行，导致延迟变化、带宽热点变化。
  - 某些前缀在对端的 best path 改变，可能引发局部不可达或会话抖动（路径依赖）。
  - 本端邻居通常仍 Established。
- 诊断步骤（工具/命令）：
  1. 本端配置审计（出方向策略）：`node_execute()`
     - `node="{router_local}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端查看前缀属性：`node_execute()`
     - `node="{router_peer}"`
     - `command='vtysh -c "show ip bgp {target_network}"'`
  3. 对端会话状态（可选）：`node_execute()`
     - `node="{router_peer}"`
     - `command='vtysh -c "show ip bgp summary"'
- 参数说明：
  - `{router_local}`：发布侧/注入 MED 的路由器
  - `{router_peer}`：接收侧路由器
  - `{target_network}`：被发布的业务前缀
- 关键判据：
  - 本端 running-config 存在对邻居出方向 `route-map MED out` 且 `set metric 9999`；
  - 对端 `show ip bgp {target_network}` 明确出现 `metric 9999` => 确诊 MED 异常升高。
  - 若对端未见新 MED：可能未 clear 会话或策略未生效，需回查配置绑定与会话刷新。

---

# ospf_passive_interface (frr 路由器) | ospf_enterprise
- 典型现象：
  - 原本正常的 OSPF 邻居突然消失，相关区域路由减少，导致部分网段不可达/绕行。
  - 物理链路/接口仍 up，能 ping 对端接口 IP，但 OSPF 不再建邻或邻居超时。
  - 业务表现为局部网络黑洞或收敛后路径改变。
- 诊断步骤（工具/命令）：
  1. 配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 接口 OSPF 状态：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf interface {interface}"'`
  3. 邻居列表（可选）：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
- 参数说明：
  - `{router}`：目标 OSPF 路由器
  - `{interface}`：互联接口名（如 toc2_1）
- 关键判据：
  - running-config 的 `router ospf` 下出现 `passive-interface {interface}`；
  - `show ip ospf interface` 显示 `No Hellos (Passive interface)` => 确诊 OSPF 接口静默。

# ospf_cost_spike (frr 路由器) | ospf_enterprise
- 典型现象：
  - 大规模路径切换：流量绕行，时延上升或链路拥塞热点迁移。
  - 某些目的网段仍可达但路径明显变长；少数情况下可能出现短暂不可达（重收敛）。
  - OSPF 邻居通常仍存在（只是成本改变）。
- 诊断步骤（工具/命令）：
  1. 配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 接口成本核对：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf interface {interface}"'`
- 参数说明：
  - `{router}`：目标路由器
  - `{interface}`：被调高 cost 的接口
- 关键判据：
  - 配置中出现异常高 `ip ospf cost 65000`（或明显高值），且接口 OSPF 信息中 `Cost: 65000` => 确诊 OSPF cost 突增。
  - 若 cost 正常但仍绕行：排查其他链路 cost 或邻居掉线导致拓扑变化。

# ospf_daemon_crash (frr 路由器) | ospf_enterprise
- 典型现象：
  - 该路由器“突然失去所有 OSPF 路由”，邻居全部消失；跨网段大量不通或绕行。
  - 物理链路可能正常，但 OSPF 控制面不可用。
  - `vtysh` 可能提示 OSPF 未运行。
- 诊断步骤（工具/命令）：
  1. 邻居检查：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
  2. 进程核对：`node_execute()`
     - `node="{router}"`
     - `command="ps aux"`
- 参数说明：
  - `{router}`：目标 OSPF 路由器
- 关键判据：
  - `show ip ospf neighbor` 返回 `OSPF is not running`/明显异常，且 `ps aux` 看不到 `ospfd` 进程（而 `zebra` 可能仍在）=> 确诊 OSPF 进程崩溃。
  - 若 `ospfd` 在但邻居少：更像 ACL/定时器/认证错配等配置问题。

# acl_blocking_ospf_traffic (frr 路由器) | ospf_enterprise
- 典型现象：
  - 物理链路 up，IP 层对端可达，但 OSPF 邻居逐渐超时消失（需要等待 Dead Interval）。
  - 该链路相关路由逐渐减少，最终部分网段不可达。
  - 业务表现为“过一会儿才坏”，具有延迟性。
- 诊断步骤（工具/命令）：
  1. INPUT 链规则检查：`node_execute()`
     - `node="{router}"`
     - `command="iptables -L INPUT -n"`
  2. 邻居状态：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
  3. 接口状态（可选）：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf interface"'`
- 参数说明：
  - `{router}`：被注入 ACL 的路由器
- 关键判据：
  - `iptables -L INPUT -n` 中存在协议号 `89` 的 `DROP` 规则，且随后 OSPF 邻居异常/减少/消失，而接口仍 up => 确诊 ACL 阻断 OSPF 流量。
  - 若无 ACL：排查 passive-interface、hello/timer/area/auth 错配。

# ospf_neighbor_misconfig (frr 路由器) | ospf_enterprise
- 典型现象：
  - 两端接口互通但邻居始终起不来，或邻居反复 Full/Down 抖动。
  - 常见于 Hello/Dead 定时器不一致。
  - 业务表现为相关区域路由学习失败，跨区域不可达或绕行。
- 诊断步骤（工具/命令）：
  1. 本端接口定时器：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show ip ospf interface {interface_a}"'`
  2. 对端接口定时器：`node_execute()`
     - `node="{router_b}"`
     - `command='vtysh -c "show ip ospf interface {interface_b}"'`
  3. 邻居观察（可选）：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
- 参数说明：
  - `{router_a}`、`{router_b}`：链路两端路由器
  - `{interface_a}`、`{interface_b}`：互联接口名
- 关键判据：
  - 两端 `show ip ospf interface` 显示 Hello/Dead 定时器不一致（如一端 `Hello 99s` 另一端 `Hello 10s`）=> 可直接确诊邻居错配已注入成功。
  - 邻居不一定立刻掉线；以定时器不一致为核心判据。

# ospf_area_misconfig (frr 路由器) | ospf_enterprise
- 典型现象：
  - 某条互联链路两端区域不一致，导致邻接无法建立或路由传播异常。
  - 可能出现“部分区域互通、部分区域不通”，或 ABR 行为异常。
  - 业务表现为部分网段突然不可达/绕行。
- 诊断步骤（工具/命令）：
  1. 运行配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 邻居状态：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
- 参数说明：
  - `{router}`：疑似区域错配的路由器
- 关键判据：
  - running-config 中同一接口网段被宣告到异常区域（如 `area 99`），并伴随相关邻居异常/减少/无法建立 => 确诊 OSPF 区域错配。
  - 若邻居仍 Full：可能错配发生在其他链路，需换节点/接口继续审计。

# ospf_auth_misconfig (frr 路由器) | ospf_enterprise
- 典型现象：
  - IP 层对端可达，但 OSPF 邻居起不来或突然掉线。
  - 常见于一端开启 message-digest 认证、对端未开启或密钥不一致。
  - 业务表现为该链路相关路由消失，跨网段不可达或绕行。
- 诊断步骤（工具/命令）：
  1. 本端配置检查：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端配置对照：`node_execute()`
     - `node="{router_b}"`
     - `command='vtysh -c "show running-config"'`
  3. 邻居状态（可选）：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show ip ospf neighbor"'`
- 参数说明：
  - `{router_a}`、`{router_b}`：链路两端路由器
- 关键判据：
  - 一端接口存在 `ip ospf authentication message-digest` 且配置了 `ip ospf message-digest-key ... md5 {key}`，而对端对应接口未配置认证/或 key 不一致 => 确诊 OSPF 认证错配。
  - 若双方都一致仍不通：排查 ACL 阻断协议 89、MTU、Hello/area 等其他参数。

---

# rip_passive_interface (frr 路由器) | rip_internet
- 典型现象：
  - 对端逐渐学不到经该接口发布的 RIP 路由；跨网段部分前缀消失。
  - 初期可能仍可达（路由未老化），一段时间后逐渐不可达。
  - 业务表现为“慢慢坏掉/路由逐步减少”。
- 诊断步骤（工具/命令）：
  1. 配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端路由表观察（可选）：`node_execute()`
     - `node="{peer_router}"`
     - `command='vtysh -c "show ip route"'`
- 参数说明：
  - `{router}`：被设置为 passive 的 RIP 路由器
  - `{peer_router}`：相邻 RIP 路由器
- 关键判据：
  - running-config 中出现 `router rip` 下的 `passive-interface {interface}` => 可判定 RIP 接口静默已注入成功。
  - 对端路由减少是增强佐证，但不要求立即发生（受 RIP 老化影响）。

# rip_route_filter (frr 路由器) | rip_internet
- 典型现象：
  - 某方向 RIP 更新被过滤，导致对端学不到路由；远端网段不可达。
  - 初期可能仍有旧路由，随后逐渐消失。
  - 业务表现为特定区域/方向的前缀“对端永远学不到”。
- 诊断步骤（工具/命令）：
  1. 配置审计 ACL 与 distribute-list：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端路由表验证（可选）：`node_execute()`
     - `node="{peer_router}"`
     - `command='vtysh -c "show ip route"'`
- 参数说明：
  - `{router}`：注入过滤策略的路由器
  - `{peer_router}`：接收端路由器
- 关键判据：
  - 配置同时出现 `access-list 99 deny any` 与 `distribute-list 99 out` => 确诊 RIP 路由过滤已注入。
  - 对端丢路由是增强佐证，但需考虑 RIP 老化时间。

# rip_metric_offset (frr 路由器) | rip_internet
- 典型现象：
  - 某些 RIP 前缀传播多跳后“变成不可达”（度量接近/达到 16）。
  - 表现为远端网段偶尔可达、再远一些就不可达；或对端不安装该路由。
  - 业务表现为跨越多跳的网络访问失败。
- 诊断步骤（工具/命令）：
  1. 配置审计 offset-list：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端路由观察（可选）：`node_execute()`
     - `node="{peer_router}"`
     - `command='vtysh -c "show ip route"'`
- 参数说明：
  - `{router}`：被注入度量偏移的路由器
  - `{peer_router}`：相邻 RIP 路由器
- 关键判据：
  - running-config 中存在 `access-list 98 permit any` 与 `offset-list 98 out 15` => 确诊 RIP 度量值篡改已注入。
  - 对端路由不出现/传播异常为辅证，但不应仅凭短时间无变化否定注入。

# acl_blocking_rip_traffic (frr 路由器) | rip_internet
- 典型现象：
  - RIP 更新收不到：邻居学不到新路由，老路由逐渐老化消失。
  - 初期看起来正常，随后路由数量逐步减少。
  - 业务表现为“过一阵子网段不可达”，且多为多个网段一起变差。
- 诊断步骤（工具/命令）：
  1. INPUT 链规则检查：`node_execute()`
     - `node="{router}"`
     - `command="iptables -L INPUT -n"`
  2. 路由表观察（可选）：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip route"'`
- 参数说明：
  - `{router}`：被注入 ACL 的 RIP 路由器
- 关键判据：
  - `iptables -L INPUT -n` 存在 `udp dpt:520` 的 `DROP` 规则 => 确诊 ACL 阻断 RIP 流量已注入。
  - 后续 RIP 学习路由减少为增强佐证（需考虑 RIP 老化）。

# rip_version_mismatch (frr 路由器) | rip_internet
- 典型现象：
  - 邻居之间路由传播异常、部分网段消失或聚合异常。
  - 一端显示使用 RIPv1，另一端仍是 RIPv2；可能出现 BadPackets 增加。
  - 业务表现为部分目的网段不可达或不稳定。
- 诊断步骤（工具/命令）：
  1. 本端 RIP 状态：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show ip rip status"'`
  2. 对端 RIP 状态对照：`node_execute()`
     - `node="{router_b}"`
     - `command='vtysh -c "show ip rip status"'`
  3. 配置审计（可选）：`node_execute()`
     - `node="{router_a}"`
     - `command='vtysh -c "show running-config"'`
- 参数说明：
  - `{router_a}`、`{router_b}`：RIP 邻居两端路由器
- 关键判据：
  - 一端 status 显示 `send version 1, receive version 1`（或明确 `version 1`），另一端仍为 `version 2` => 确诊 RIP 版本错配。
  - 若版本一致但仍传播异常：排查 ACL 520、过滤、度量偏移、定时器异常。

# rip_timer_misconfig (frr 路由器) | rip_internet
- 典型现象：
  - 路由收敛极慢：故障恢复/链路切换后长时间不更新。
  - 对端长时间保留陈旧路由或迟迟不老化。
  - 业务表现为网络变化后“几十分钟才恢复”，甚至持续错误路径。
- 诊断步骤（工具/命令）：
  1. RIP 状态定时器检查：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show ip rip status"'`
  2. 配置审计：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
- 参数说明：
  - `{router}`：目标路由器
- 关键判据：
  - status 中出现 `Sending updates every 999 seconds`、`Timeout after 999 seconds` 等异常大值，且配置含 `timers basic 999 999 999` => 确诊 RIP 计时器篡改。

# rip_network_withdraw (frr 路由器) | rip_internet
- 典型现象：
  - 原本可达的某个直连业务网段突然“从全网消失”，远端到该网段不可达。
  - 对端路由表不再包含该前缀；业务主机 ping 该网段主机失败。
  - 影响通常集中在被撤销发布的网段。
- 诊断步骤（工具/命令）：
  1. 本端配置检查：`node_execute()`
     - `node="{router}"`
     - `command='vtysh -c "show running-config"'`
  2. 对端路由表验证：`node_execute()`
     - `node="{downstream_router}"`
     - `command='vtysh -c "show ip route"'`
  3. 业务探测（可选）：`ping_by_ip()`
     - `src_node="{remote_host}"`
     - `dst_ip="{host_in_withdrawn_net_ip}"`
- 参数说明：
  - `{router}`：撤销 RIP network 的路由器
  - `{downstream_router}`：依赖该宣告学习路由的下游路由器
  - `{remote_host}`：远端业务主机
  - `{host_in_withdrawn_net_ip}`：被撤销网段内的一台主机 IP
- 关键判据：
  - running-config 的 `router rip` 下不再包含 `network {network}`，且对端路由表缺少该网段 => 确诊 RIP 路由撤销。
  - 远端 ping 报 `Destination Net Unreachable` 为增强佐证。

---

# p4_bmv2_process_crash (bmv2 交换机) | p4_star
- 典型现象：
  - 途经该 P4 交换机的流量“整体中断”，多对主机同时不通。
  - 交换机控制面 CLI（thrift）无法连接，table dump 报拒绝连接。
  - 主机可能表现为同网段/跨网段均不通（取决于拓扑）。
- 诊断步骤（工具/命令）：
  1. Thrift CLI 连通性验证：`bmv2_execute()`
     - `node="{p4_switch}"`
     - `cli_cmd="table_dump {table_name}"`
  2. 获取表名（若不确定）：`find_p4_ipv4_lpm_table()`
     - `node="{p4_switch}"`
- 参数说明：
  - `{p4_switch}`：BMv2/P4 交换机名称（如 s1）
  - `{table_name}`：IPv4 LPM 表名（常见 `MyIngress.ipv4_lpm`，不确定就先查）
- 关键判据：
  - `bmv2_execute` 返回 `Could not connect` / `Connection refused` 等无法连接 thrift CLI => 确诊 BMv2 进程崩溃。
  - 若 CLI 可连但业务不通：转查表项 drop/缺失/错误转发或主机侧故障。

# p4_table_drop (bmv2 交换机) | p4_star
- 典型现象：
  - “到某个特定 IP”完全不通（或丢包严重），其他目标可能正常。
  - 多从同一源发往同一目的持续失败，具有稳定性。
  - 交换机表项中该目的对应动作变成 drop。
- 诊断步骤（工具/命令）：
  1. 确认 LPM 表名：`find_p4_ipv4_lpm_table()`
     - `node="{p4_switch}"`
  2. 转发表核查：`bmv2_execute()`
     - `node="{p4_switch}"`
     - `cli_cmd="table_dump {table_name}"`
  3. 业务验证：`ping_by_ip()`
     - `src_node="{src_host}"`
     - `dst_ip="{dst_ip}"`
- 参数说明：
  - `{p4_switch}`：目标 P4 交换机
  - `{table_name}`：IPv4 LPM 表名
  - `{src_host}`：源主机
  - `{dst_ip}`：被 drop 的目标主机 IP
- 关键判据：
  - `table_dump` 中 `{dst_ip}` 匹配项动作明确为 `MyIngress.drop`（或程序实际 drop 动作名），且 ping 全失败 => 确诊 P4 表项级 DROP 注入。

# p4_wrong_forwarding (bmv2 交换机) | p4_star
- 典型现象：
  - 到某特定 IP 不通，但交换机并未 drop，而是“转发到错误端口/错误下一跳 MAC”。
  - 现象像黑洞：ping 超时，且对端无响应。
  - 表项动作仍为 forward，但参数异常（MAC=00:00...，端口=99 等）。
- 诊断步骤（工具/命令）：
  1. 确认表名：`find_p4_ipv4_lpm_table()`
     - `node="{p4_switch}"`
  2. 业务验证：`ping_by_ip()`
     - `src_node="{src_host}"`
     - `dst_ip="{dst_ip}"`
  3. 表项参数核查：`bmv2_execute()`
     - `node="{p4_switch}"`
     - `cli_cmd="table_dump {table_name}"`
- 参数说明：
  - `{p4_switch}`：目标 P4 交换机
  - `{table_name}`：IPv4 LPM 表名
  - `{src_host}`：源主机
  - `{dst_ip}`：异常目标 IP
- 关键判据：
  - ping 失败，同时 `table_dump` 显示对应项仍是 `MyIngress.ipv4_forward`（或实际 forward 动作），但动作参数为异常 MAC/异常 egress 端口（如端口 99 显示为十六进制 `63`）=> 确诊 P4 错误转发。

# p4_table_entry_missing (bmv2 交换机) | p4_star
- 典型现象：
  - 原本互通的两台主机突然彻底不通，且更像“没有匹配项”导致走默认行为。
  - 若默认动作是 drop，则表现为稳定全丢；若默认是其他行为则表现不同。
  - 表 dump 中缺少目标前缀/主机前缀项。
- 诊断步骤（工具/命令）：
  1. 确认表名：`find_p4_ipv4_lpm_table()`
     - `node="{p4_switch}"`
  2. 表项核对：`bmv2_execute()`
     - `node="{p4_switch}"`
     - `cli_cmd="table_dump {table_name}"`
  3. 业务验证（可选）：`ping_by_ip()`
     - `src_node="{src_host}"`
     - `dst_ip="{dst_ip}"`
- 参数说明：
  - `{p4_switch}`：目标 P4 交换机
  - `{table_name}`：IPv4 LPM 表名
  - `{src_host}`：源主机
  - `{dst_ip}`：目标主机 IP（应存在 /32 项或被更粗前缀覆盖）
- 关键判据：
  - `table_dump` 中找不到 `{dst_ip}/32`（或对应应匹配的前缀项）且业务失败 => 确诊 P4 表项缺失。
  - 注意：若存在更粗前缀覆盖，需结合实际匹配优先级判断是否“缺失”。

# p4_default_action_drop (bmv2 交换机) | p4_star
- 典型现象：
  - “新流量/未显式配置的目的”全部不通；已有精确表项的流量可能仍通。
  - 故障呈现选择性：某些目的正常、某些目的全丢。
  - `table_dump` 默认项显示 drop。
- 诊断步骤（工具/命令）：
  1. 确认表名：`find_p4_ipv4_lpm_table()`
     - `node="{p4_switch}"`
  2. 默认动作检查：`bmv2_execute()`
     - `node="{p4_switch}"`
     - `cli_cmd="table_dump {table_name}"`
- 参数说明：
  - `{p4_switch}`：目标交换机
  - `{table_name}`：目标表名（IPv4 LPM）
- 关键判据：
  - dump 输出中 `Dumping default entry` 下出现 `Action entry: MyIngress.drop -`（或等价 drop 动作）=> 确诊默认动作改为 DROP。
  - 若默认非 drop 但业务仍不通：排查表项缺失/错误转发/主机侧故障。

---

# sdn_controller_crash (ryu 控制器) | sdn_openflow
- 典型现象：
  - SDN 网络失去集中控制：新主机/新流无法通信，已有流可能逐渐失效（取决于交换机 fail-mode 与流表老化）。
  - 控制器南向端口（6653/6633）不再监听；控制器进程消失。
  - 多对主机间互通同时异常，呈现“面状故障”。
- 诊断步骤（工具/命令）：
  1. 监听端口检查：`node_execute()`
     - `node="{controller}"`
     - `command="ss -tln"`
  2. 进程检查：`node_execute()`
     - `node="{controller}"`
     - `command="ps aux"`
  3. 全网可达性（可选）：`get_reachability()`
     - （无参数）
- 参数说明：
  - `{controller}`：Ryu 控制器节点名称
- 关键判据：
  - `ss -tln` 看不到 `:6653`/`:6633` 监听，且 `ps aux` 无 `ryu-manager`/相关 Python 进程 => 确诊控制器崩溃。
  - 若端口在监听但业务不通：排查 OVS 断连、协议错配、全局 drop 流表等交换机侧故障。

# ovs_disconnect (ovs 交换机) | sdn_openflow
- 典型现象：
  - 单台交换机不再接受控制器下发策略；该交换机相关主机互通异常或退化为本地行为（取决于 fail-mode/现有流表）。
  - 控制器仍正常，其他交换机正常。
  - `ovs-vsctl show` 中 controller 字段缺失或无连接状态。
- 诊断步骤（工具/命令）：
  1. 网桥列表：`ovs_list_bridges()`
     - `node="{ovs_switch}"`
  2. OVS 总览检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-vsctl show"`
  3. 控制器端口对照（可选）：`node_execute()`
     - `node="{controller}"`
     - `command="ss -tln"`
- 参数说明：
  - `{ovs_switch}`：OVS 交换机节点
  - `{controller}`：控制器节点
- 关键判据：
  - 控制器端口仍监听，但该 OVS 的 `ovs-vsctl show` 中已无 controller 绑定（或显示未连接）=> 确诊 OVS 断开控制器连接。
  - 若仍绑定但不工作：排查 southbound_wrong_controller / 协议错配 / fail-mode secure。

# ovs_global_drop (ovs 交换机) | sdn_openflow
- 典型现象：
  - 途经该交换机的所有流量几乎全部中断（ICMP/TCP/UDP 都不通）。
  - 多对主机同时不通，且集中在该交换机域内。
  - dump-flows 中出现超高优先级全局 drop 规则。
- 诊断步骤（工具/命令）：
  1. 网桥列表：`ovs_list_bridges()`
     - `node="{ovs_switch}"`
  2. 流表检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-ofctl dump-flows {bridge_name}"`
  3. 业务验证（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 4 -W 2 {target_ip}"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS 交换机
  - `{bridge_name}`：目标网桥名（如 init-br0）
  - `{host_node}`：任一受影响主机
  - `{target_ip}`：任一应可达目标
- 关键判据：
  - dump-flows 中存在 `priority=65535` 且 `actions=drop` 的规则（且通常无匹配字段）=> 确诊 OVS 全局 DROP 流表。
  - 若没有该规则但仍不通：排查控制器崩溃/断连或其他高优先级规则。

# southbound_wrong_controller (ovs 交换机) | sdn_openflow
- 典型现象：
  - OVS 控制器地址被改错：控制器实际健康，但该 OVS 永远连不上。
  - 单台交换机域内业务异常；其他交换机可能正常。
  - `ovs-vsctl show` 显示 controller 指向错误 IP。
- 诊断步骤（工具/命令）：
  1. OVS 配置检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-vsctl show"`
  2. 控制器端口对照：`node_execute()`
     - `node="{controller}"`
     - `command="ss -tln"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS 交换机
  - `{controller}`：实际控制器节点
- 关键判据：
  - 控制器端口仍监听，但 OVS 侧 controller 地址变为明显错误地址（如 `tcp:192.168.254.254:6653`）且连接状态异常 => 确诊南向控制器地址错配。

# southbound_protocol_mismatch (ovs 交换机) | sdn_openflow
- 典型现象：
  - 控制器与 OVS “能连但说不通”或无法下发策略：交换机协议版本被降级/错配。
  - 业务表现为策略失效、流表不更新、新流不通。
  - `ovs-vsctl` 中显示 protocols=OpenFlow10 等，与控制器期望不一致。
- 诊断步骤（工具/命令）：
  1. 协议版本检查：`ovs_get_bridge_protocols()`
     - `node="{ovs_switch}"`
     - `bridge_name="{bridge_name}"`
  2. OVS 总览：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-vsctl show"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS 交换机
  - `{bridge_name}`：网桥名
- 关键判据：
  - `ovs_get_bridge_protocols` 显示仅支持 `OpenFlow10`（或与控制器要求版本不一致），并伴随控制连接异常/策略无法下发 => 确诊南向协议错配。
  - 若协议正常但策略仍失效：排查 flow_rule_shadowing、全局 drop、控制器异常。

# flow_rule_shadowing (ovs 交换机) | sdn_openflow
- 典型现象：
  - 网络策略“整体失效/退化”：流量不再按控制器预期路径转发，可能变成普通二层转发。
  - 一些被隔离/ACL 的流量突然放通，或路径选择异常。
  - dump-flows 中出现高优先级通配 `actions=normal`。
- 诊断步骤（工具/命令）：
  1. 网桥列表：`ovs_list_bridges()`
     - `node="{ovs_switch}"`
  2. 流表检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-ofctl dump-flows {bridge_name}"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS
  - `{bridge_name}`：网桥名
- 关键判据：
  - dump-flows 中存在 `priority=1000 actions=normal` 的宽泛规则（覆盖控制器细粒度规则）=> 确诊流表规则覆盖（shadowing）。
  - 若无该规则但策略仍异常：排查控制器应用逻辑、协议错配、控制器崩溃。

# flow_rule_loop (ovs 交换机) | sdn_openflow
- 典型现象：
  - 出现环路/自回环：带宽被迅速挤占，延迟飙升，丢包严重。
  - 相关主机 ping 丢包或完全不通；交换机 CPU/队列可能升高（视环境）。
  - dump-flows 出现 `in_port=X,actions=output:X` 的回环规则。
- 诊断步骤（工具/命令）：
  1. 流表检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-ofctl dump-flows {bridge_name}"`
  2. 业务探测（可选）：`node_execute()`
     - `node="{host_node}"`
     - `command="ping -c 4 -W 2 {target_ip}"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS
  - `{bridge_name}`：网桥名
  - `{host_node}`：受影响主机
  - `{target_ip}`：任一目标 IP
- 关键判据：
  - dump-flows 中存在高优先级（如 `priority=2000`）的 `in_port=1,actions=output:1`（或其他端口自回环）=> 确诊流表环路注入。
  - 若丢包严重但无回环规则：排查链路丢包/带宽限制/广播风暴等其他原因。

# ovs_fail_secure (ovs 交换机) | sdn_openflow
- 典型现象：
  - 控制器短暂异常或断连后，交换机不再进行本地兜底转发，业务立即中断并持续。
  - 与控制器状态强相关：一旦控制面异常，数据面不 fallback。
  - `ovs-vsctl` 显示 `fail_mode: secure`。
- 诊断步骤（工具/命令）：
  1. OVS 配置检查：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-vsctl show"`
  2. bridge 详细信息：`node_execute()`
     - `node="{ovs_switch}"`
     - `command="ovs-vsctl list bridge"`
- 参数说明：
  - `{ovs_switch}`：目标 OVS
- 关键判据：
  - `fail_mode` 字段为 `secure` => 确认 OVS Fail Mode Secure 注入成功。
  - 若 fail_mode 为 secure 且控制器断连时业务立即全断：可作为强佐证（但确诊以 fail_mode 字段为准）。

---

# ai_service_crash (ubuntu 主机) | ai_inference
- 典型现象：
  - AI 助手突然不再回复；客户端请求连接失败/连接被拒绝/超时。
  - 底层网络可能正常（能 ping 通算力节点），但 8000 端口无服务监听。
  - 服务端进程（python3 real_llm）消失。
- 诊断步骤（工具/命令）：
  1. 业务探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
  2. 端口监听检查：`node_execute()`
     - `node="{server_node}"`
     - `command="ss -tln"`
  3. 进程检查（可选）：`node_execute()`
     - `node="{server_node}"`
     - `command="ps aux"`
- 参数说明：
  - `{client_node}`：发起推理请求的客户端节点
  - `{server_node}`：AI 推理服务所在算力节点
  - `{server_ip}`：AI 服务端 IP
- 关键判据：
  - `test_ai_inference` 连接失败/超时，且服务端 `ss -tln` 看不到 `:8000` 监听 => 确诊 AI 推理进程崩溃。
  - 若 8000 在监听但仍失败：转查 iptables 端口阻断、CPU/内存资源耗尽或中间节点 RST/黑洞。

# compute_cpu_starvation (ubuntu 主机) | ai_inference
- 典型现象：
  - AI “吐字极慢”、请求延迟显著上升，甚至客户端超时。
  - 服务端系统负载很高，交互卡顿；同机其他服务也变慢。
  - 网络层 ping 可能仍正常，但应用层响应慢。
- 诊断步骤（工具/命令）：
  1. 压力进程巡检：`check_ai_processes()`
     - `node="{server_node}"`
  2. CPU 资源快照：`node_execute()`
     - `node="{server_node}"`
     - `command="top -b -n 1"`
  3. 业务时延探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
- 参数说明：
  - `{server_node}`：算力节点
  - `{client_node}`：客户端节点
  - `{server_ip}`：服务端 IP
- 关键判据：
  - `check_ai_processes` 中存在 `stress-ng`/多个 `stress-ng-cpu`，`top` 显示其持续高占用 CPU，且推理请求耗时显著上升/失败 => 确诊算力节点 CPU 满载。
  - 注入命令可能返回超时不代表失败；以进程与资源占用为准。

# compute_memory_exhaustion (ubuntu 主机) | ai_inference
- 典型现象：
  - 大并发或大请求时 AI 服务突然无响应、频繁超时，甚至进程被 OOM 杀死（视环境）。
  - 系统可用内存（available）明显下降，swap（若有）飙升。
  - 网络层 ping 可能正常，但应用层不响应或极慢。
- 诊断步骤（工具/命令）：
  1. 压力进程巡检：`check_ai_processes()`
     - `node="{server_node}"`
  2. 内存监控：`node_execute()`
     - `node="{server_node}"`
     - `command="free -m"`
  3. 资源监控：`node_execute()`
     - `node="{server_node}"`
     - `command="top -b -n 1"`
  4. 业务探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
- 参数说明：
  - `{server_node}`：AI 算力节点名称
  - `{client_node}`：客户端节点名称
  - `{server_ip}`：AI 服务端 IP
- 关键判据：
  - 存在 `stress-ng-vm` 进程且 `free -m` 显示 available 显著耗尽，同时推理大量超时/失败 => 确诊算力节点内存溢出。
  - 若无压力进程但内存低：可能是模型/业务真实占用或内存泄漏，需进一步定位（不应误判为注入故障）。

# inference_port_blocked (ubuntu 主机) | ai_inference
- 典型现象：
  - 能 ping 通服务器，但推理 API 全部超时/无法连接。
  - 服务端 8000 可能在监听，但请求到达不了（被 INPUT 链 DROP）。
  - 浏览器/客户端表现为连接卡住（DROP）而非立即拒绝。
- 诊断步骤（工具/命令）：
  1. 业务探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
  2. 服务端防火墙检查：`node_execute()`
     - `node="{server_node}"`
     - `command="iptables -L INPUT -n"`
  3. 底层连通性对照：`ping_by_ip()`
     - `src_node="{client_node}"`
     - `dst_ip="{server_ip}"`
- 参数说明：
  - `{client_node}`：客户端
  - `{server_node}`：推理服务所在主机
  - `{server_ip}`：推理服务 IP
- 关键判据：
  - ping 正常，但 `test_ai_inference` 超时/失败，且服务端 INPUT 链存在 `tcp dpt:8000 DROP` => 确诊推理端口被防火墙阻断。
  - 若无 DROP 规则但仍不通：排查中间转发节点黑洞/RST、服务进程崩溃、路由不通。

# tcp_rst_injection (frr 路由器) | ai_inference
- 典型现象：
  - 客户端请求不是超时，而是“连接被重置/Read error/Connection reset by peer”一类快速失败。
  - ping 通服务器（ICMP 正常），但 TCP 会话很快被 RST 打断。
  - 常表现为偶发或稳定的“刚连上就断”。
- 诊断步骤（工具/命令）：
  1. 中间节点 FORWARD 链检查：`node_execute()`
     - `node="{transit_router}"`
     - `command="iptables -L FORWARD -n"`
  2. ICMP 连通性对照：`ping_by_ip()`
     - `src_node="{client_node}"`
     - `dst_ip="{server_ip}"`
  3. 业务探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
- 参数说明：
  - `{transit_router}`：客户端到服务端路径上的中间转发路由器
  - `{client_node}`：客户端节点
  - `{server_ip}`：服务端 IP
- 关键判据：
  - FORWARD 链存在 `REJECT --reject-with tcp-reset` 规则，且 ping 正常但推理请求表现为连接被重置/快速失败 => 确诊 TCP RST 注入。
  - 若 FORWARD 无此规则但仍 reset：可能为服务端主动关闭/代理层故障，需进一步查服务端日志与监听状态。

# cross_layer_traffic_blackhole (frr 路由器) | ai_inference
- 典型现象：
  - “能 ping 通，但推理请求一直超时”，并且现象稳定复现。
  - 更像中间路径对 `{server_ip}:8000` 定向丢弃（黑洞），而非服务端崩溃。
  - 其他端口/其他业务可能正常（取决于丢弃规则粒度）。
- 诊断步骤（工具/命令）：
  1. 业务探测：`test_ai_inference()`
     - `client_node="{client_node}"`
     - `server_ip="{server_ip}"`
     - `port=8000`
  2. 中间节点 FORWARD 链检查：`node_execute()`
     - `node="{transit_router}"`
     - `command="iptables -L FORWARD -n"`
  3. ICMP 对照（可选）：`ping_by_ip()`
     - `src_node="{client_node}"`
     - `dst_ip="{server_ip}"`
- 参数说明：
  - `{client_node}`：客户端节点
  - `{server_ip}`：AI 服务端 IP
  - `{transit_router}`：连接 server 的接入路由或中间转发路由器
- 关键判据：
  - 推理业务持续超时，同时中间节点 FORWARD 链存在针对 `-d {server_ip} -p tcp --dport 8000 -j DROP` 的规则，且 ping 正常或基本正常 => 确诊跨层流量黑洞（算网隔离/跨层路由黑洞）。
  - 若无该规则：转查服务端 INPUT 链端口阻断、服务崩溃、链路丢包/延迟导致应用超时。