# **链路丢包 (Link Loss)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：链路层故障 (Link Level)
   - 期待故障：link_loss
   - 注入方式：
     使用工具：`tc_set(host_name, link, loss)`
     步骤：参数 `host_name` 填入目标主机名，参数 `link` 填入目标网络链路名称（通常即主机的网卡接口名，如 `eth0`）。参数 `loss` 填入丢包率百分比（为保证效果明显，建议填入 `50`，代表 50% 丢包率）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称。依次执行两步：
     1. 参数 `command` 填入 `tc qdisc show` 查看底层队列规则。
     2. 参数 `command` 填入 `ping -c 10 -W 2 {target_ip}` 进行通信测试。
     检测思路：若 Ping 测试出现明显的丢包率（如大于 0 且小于 100%），同时第一步 `tc qdisc show` 输出中包含 `netem` 规则且明确带有 `loss` 关键字与百分比数值，即可确诊为链路丢包故障。如果 100% 丢包且没有 loss 规则，则为路由或防误判拦截，需排除此类故障。
   - 故障表现描述：用户反馈某节点出现严重丢包。

# **链路延迟 (Link Latency)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：链路层故障 (Link Level)
   - 期待故障：link_latency
   - 注入方式：
     使用工具：`tc_set(host_name, link, delay_ms)`
     步骤：参数 `host_name` 填入目标主机名，参数 `link` 填入目标网络链路名称。参数 `delay_ms` 填入延迟时间（建议填入 `100` 或更大的数值，单位为毫秒）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称。依次执行：
     1. 参数 `command` 填入 `tc qdisc show` 查看底层队列规则。
     2. 参数 `command` 填入 `ping -c 10 -W 2 {target_ip}` 进行通信测试。
     检测思路：若 Ping 测试的平均延迟（`avg` rtt）异常偏高（例如 > 50ms），但抖动（`mdev`）极小，表明这是一个稳定的高延迟。结合 `tc qdisc show` 输出中含有 `netem` 规则和 `delay` 参数，即可确诊。
   - 故障表现描述：用户反馈通信延迟极高。

# **链路抖动 (Link Jitter)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：链路层故障 (Link Level)
   - 期待故障：link_jitter
   - 注入方式：
     使用工具：`tc_set(host_name, link, delay_ms, jitter_ms)`
     步骤：参数 `host_name` 填入目标主机名，参数 `link` 填入链路名。注意：要产生抖动，必须同时设置基础延迟和抖动参数！参数 `delay_ms` 填入 `100`，参数 `jitter_ms` 填入 `50`（单位均为毫秒）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称。依次执行：
     1. 参数 `command` 填入 `tc qdisc show` 检查规则。
     2. 参数 `command` 填入 `ping -c 10 -W 2 {target_ip}` 收集延迟样本。
     检测思路：重点观察 Ping 输出最后一行的 `mdev`（平均偏差）数值。局域网正常 `mdev` 极小，若 `mdev` 显著偏高（如 > 10ms），表现出延迟忽高忽低，且 `tc qdisc show` 规则中带有 `delay` 及其后的数值（代表抖动区间），即可确诊为链路抖动故障。
   - 故障表现描述：用户反馈某主机网络忽快忽慢，很不稳定。

# **链路带宽限制 (Link Bandwidth)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：链路层故障 (Link Level)
   - 期待故障：link_bandwidth
   - 注入方式：
     使用工具：`tc_set(host_name, link, bw_kbps)`
     步骤：参数 `host_name` 填入目标主机名，参数 `link` 填入链路名。参数 `bw_kbps` 填入限制的带宽大小（建议填入较小的值如 `100`，单位为 kbps，以产生明显的限速拥塞效果）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `tc qdisc show`。
     检测思路：直接审查底层的流量控制规则输出。如果发现存在 `tbf`（令牌桶过滤器）关键字，并且包含明确的 `rate` 参数（如 `rate 100Kbit` 或类似速率限制表现），即可确诊为链路带宽限制故障。
   - 故障表现描述：用户反馈某主机传输速度被严重限流，网络拥塞严重。

---

# **IP 配置错误 (IP Misconfig)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：ip_misconfig
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称。参数 `command` 需依次分次下发三条命令：
     1. `ip addr flush dev {iface}` （`{iface}` 为与网络相连的网卡名）
     2. `ip addr add {wrong_ip} dev {iface}` （`{wrong_ip}` 填入错误的IP地址带掩码，如 `100.99.88.77/24`）
     3. `ip link set {iface} up`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip addr show {iface}`。
     检测思路：读取命令输出，提取 `inet` 字段的 IPv4 地址。如果发现没有 `inet` 字段（IP丢失），或者该 IP 与拓扑中记录的预配 IP 不一致，即可确诊为 IP 配置错误。
   - 故障表现描述：用户反馈某主机无法与同网段或其他节点正常通信，IP 可能丢失或配错。

# **默认路由缺失 (Default Route Missing)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：default_route_missing
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip route del default`。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip route show`。
     检测思路：读取主机的全局路由表。如果输出中找不到 `default via` 或 `0.0.0.0` 的条目，且网卡状态正常（非 DOWN），即可确诊默认路由缺失。
   - 故障表现描述：用户反馈某主机同网段通信正常，但跨网段通信完全不可达。

# **ARP 缓存投毒 (ARP Poisoning)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：arp_poisoning
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入要投毒的主机名称，参数 `command` 填入 `arp -s {target_ip} {fake_mac}`（`{target_ip}` 为要阻断通信的对端IP，`{fake_mac}` 为伪造MAC，如 `aa:bb:cc:dd:ee:ff`）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip neigh show`。
     检测思路：检查主机的 ARP 缓存表。若发现目标 IP 对应的状态为 `FAILED`，或者 MAC 地址出现明显的伪造（如 `aa:bb:cc:dd:ee:ff`），或在非 SDN/P4 环境下出现异常的 `PERMANENT` 静态绑定，即可确诊 ARP 投毒。
   - 故障表现描述：用户反馈某主机局域网内无法与特定目标通信。

# **接口宕机 (Interface Down)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：interface_down
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip link set {iface} down`（`{iface}` 为网卡名）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `ip link show {iface}`。
     检测思路：检查网卡的链路层状态。如果输出信息中包含明确的 `state DOWN` 字样，即可 100% 确诊物理或逻辑链路被关闭。
   - 故障表现描述：用户反馈某主机似乎彻底脱网。

# **DNS 配置错误 (DNS Error)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：dns_error
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `sh -c "echo nameserver {fake_dns} > /etc/resolv.conf"`（`{fake_dns}` 填入无效IP如 `0.1.2.3`）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `cat /etc/resolv.conf`。
     检测思路：读取 DNS 配置文件。如果 `nameserver` 指向了错误的地址（如 `0.1.2.3`）而非正常的网关或公共 DNS，即可确诊配置错误。
   - 故障表现描述：用户反馈某主机无法访问外部域名网站。

# **CPU 资源满载 (CPU Overload)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：cpu_overload
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `sh -c 'nohup stress-ng --cpu 2 --timeout 300s > /dev/null 2>&1 &'`（利用 stress-ng 规范化地打满 CPU，持续 300 秒自动释放）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标主机名称，参数 `command` 填入 `top -b -n 1 | head -n 15`。
     检测思路：审查系统进程列表。如果发现 CPU 的 `id` (空闲率) 趋近于 0，且存在 `stress-ng` 占用极高的 `%CPU`，即可确诊。
   - 故障表现描述：用户反馈某主机系统严重卡顿，业务处理缓慢。

# **主机静态路由错误 (Routing Error)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：routing_error
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `ip route add {wrong_network} via {wrong_gw}`（将特定目标网段错误指向不存在的网关）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `ip route show`。
     检测思路：对比主机路由表，如果存在指向非预期网关的可疑网段静态路由条目，即可确诊。
   - 故障表现描述：用户反馈主机无法访问特定的某个外部网段，数据包走向异常。

# **子网掩码错误 (Mask Error)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：mask_error
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称。必须依次独立调用两次工具：
     1. 第一次调用：`command` 填入 `ip addr flush dev {iface}`（清空原有IP）。
     2. 第二次调用：`command` 填入 `ip addr add {ip}/{wrong_mask} dev {iface}`（配上极小的错误子网掩码如 /30）。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `ip addr show {iface}`。
     检测思路：检查 `inet` 字段的 IP 后缀 CIDR。如果发现子网掩码与全局规划明显不符，即可确诊。
   - 故障表现描述：用户反馈同网段内的部分相邻主机无法直接通信。

# **主机端口耗尽 (Host Port Exhaustion)**
   - 适用场景：static_routing 等任意场景
   - 故障类型：主机层故障 (Host Level)
   - 期待故障：host_port_exhaustion
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `sysctl -w net.ipv4.ip_local_port_range="32768 32768"` 将可用临时端口限制为 1 个。
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入主机名称，参数 `command` 填入 `sysctl net.ipv4.ip_local_port_range`。
     检测思路：检查主机内核可用源端口范围，若该范围极窄或被锁定，确诊端口耗尽故障。
   - 故障表现描述：用户反馈主机内的应用程序抛出大量“无法分配请求的地址”或无法发起新的对外连接。

--- 

# **目标网段路由缺失 (Route Missing)**
   - 适用场景：static_routing
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：route_missing
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `ip route del {network}`。
     其中：
     - `{network}` 表示要删除的目标业务网段，必须填写“网段/掩码”格式，例如 `192.168.4.0/24`
     - 该命令适用于删除 Linux 内核路由表中的静态路由条目
     - 建议优先选择一个当前确实可达、且通过该路由器转发的远端业务网段，以保证故障现象明显
     - 在 `static_routing` 场景中，若目标是 `r1`，优先选择 `192.168.3.0/24` 或 `192.168.4.0/24`；若目标是 `r2`，优先选择 `192.168.1.0/24` 或 `192.168.2.0/24`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入同一台路由器名称，参数 `command` 填入 `ip route show`
     2. 参数 `node` 填入同一台路由器名称，参数 `command` 填入 `ip route get {target_ip}`
     其中：
     - `{target_ip}` 表示属于 `{network}` 网段内的一个具体主机 IP，例如当 `{network}` 为 `192.168.4.0/24` 时，可填 `192.168.4.2`
     检测思路：若第一步路由表中已看不到目标网段，且第二步输出出现 `unreachable`、`Network is unreachable` 等信息，即可确诊为目标网段路由缺失。
   - 故障表现描述：用户反馈某主机发往特定网段的跨网段流量完全不通，提示网络不可达。

# **静态黑洞路由 (Static Route Blackhole)**
   - 适用场景：static_routing
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：static_route_blackhole
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `ip route replace blackhole {network}`。
     其中：
     - `{network}` 表示要被黑洞化的目标业务网段，格式必须为“网段/掩码”，例如 `192.168.4.0/24`
     - `replace` 表示若原先已存在该路由则直接替换，若不存在则创建
     - 建议选择一个业务侧真实会访问的远端业务网段，以便故障效果稳定复现
     - 在 `static_routing` 场景中，若目标是 `r1`，建议黑洞 `192.168.3.0/24` 或 `192.168.4.0/24`；若目标是 `r2`，建议黑洞 `192.168.1.0/24` 或 `192.168.2.0/24`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip route show`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip route get {target_ip}`
     其中：
     - `{target_ip}` 表示 `{network}` 内一个实际测试地址，例如 `192.168.4.2`
     检测思路：若第一步路由表中出现目标网段对应的 `blackhole` 条目，则可直接确诊。第二步在黑洞场景下可能返回 `Invalid argument` 等异常输出，这也可作为辅助现象；但**以第一步路由表中明确出现 `blackhole {network}` 为最准**。
   - 故障表现描述：用户反馈某业务网段的数据包被神秘丢弃，流量有去无回。

# **数据面 ICMP 阻断 (Data Plane Drop)**
   - 适用场景：static_routing
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：data_plane_drop
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `iptables -I FORWARD -p icmp -j DROP`。
     其中：
     - `FORWARD` 表示拦截经过该路由器转发的数据流，而不是本机自产生或发往本机的流量
     - `-p icmp` 表示仅针对 ICMP 报文
     - `-j DROP` 表示直接静默丢弃
     - 该故障适合用于制造“跨网段 Ping 不通但同网段 Ping 仍正常”的现象
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `iptables -L FORWARD -n`
     2. 参数 `node` 填入业务源主机名称，参数 `command` 填入 `ping -c 4 -W 2 {target_ip}`
     3. 参数 `node` 填入同网段另一台主机名称，参数 `command` 填入 `ping -c 4 -W 2 {same_subnet_ip}`
     其中：
     - `{target_ip}` 表示需要经过该路由器转发才能访问到的对端主机 IP
     - `{same_subnet_ip}` 表示与源主机处于同一二层广播域的主机 IP
     - `-c 4` 建议发送 4 个探测包
     - `-W 2` 建议单包等待超时为 2 秒
     检测思路：若第一步可见 FORWARD 链存在针对 ICMP 的 DROP 规则，第二步跨网段 Ping 全部超时，而第三步同网段 Ping 仍正常，即可确诊数据面 ICMP 阻断。
   - 故障表现描述：用户反馈 Ping 测试全部超时，但其他 TCP 或 UDP 连接似乎正常。

# **FRR 进程宕机 (FRR Service Down)**
   - 适用场景：static_routing / ospf_enterprise
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：frr_service_down
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称，必须分两次独立执行：
     1. 参数 `command` 填入 `pkill zebra`
     2. 参数 `command` 填入 `pkill bgpd`
     其中：
     - `zebra` 是 FRR 的核心路由管理守护进程
     - `bgpd` 是 BGP 守护进程
     - 在 `static_routing` 场景中，真正关键的是杀掉 `zebra`
     - 若目标节点本来没有运行 `bgpd`，第二条命令可能无输出或无匹配，这属于正常现象，不影响故障成立
     - 按 klonet 规范，禁止使用 `&&` 拼接，必须拆分为两次 `node_execute`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip route"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `ps aux`
     检测思路：若第一步返回 `failed to connect to any daemons`、`Exiting: failed to connect to any daemons` 或等价报错，同时第二步看不到 `zebra` 进程，则即可确诊 FRR 进程宕机。若连 `bgpd` 也一起消失，则说明停得更彻底。
   - 故障表现描述：用户反馈某台路由器突然停止一切动态路由转发能力，导致局部网络瘫痪。

# **路由转发关闭 (IP Forward Disabled)**
   - 适用场景：static_routing
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：ip_forward_disabled
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入路由器名称。参数 `command` 填入 `sysctl -w net.ipv4.ip_forward=0`。
     其中：
     - `net.ipv4.ip_forward` 是 Linux 内核 IPv4 转发开关
     - 数字 `0` 表示关闭三层转发
     - 若要恢复，通常应改回 `1`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `sysctl net.ipv4.ip_forward`
     2. 参数 `node` 填入源主机名称，参数 `command` 填入 `ping -c 4 -W 2 {target_ip}`
     3. 参数 `node` 填入源主机名称，参数 `command` 填入 `ping -c 4 -W 2 {router_ip}`
     其中：
     - `{target_ip}` 应为需要经过该路由器转发才能到达的对端主机 IP
     - `{router_ip}` 应为该源主机默认网关对应的路由器接口 IP
     检测思路：若第一步输出明确为 `net.ipv4.ip_forward = 0`，第二步跨网段通信失败，而第三步源主机仍能 Ping 通本机网关接口，则即可确诊路由转发关闭。
   - 故障表现描述：用户反馈路由器本机可达，但转发经过它的业务流量全部中断。

# **路由器接口地址错误 (Router Interface IP Wrong)**
   - 适用场景：static_routing
   - 故障类型：FRR故障 (FRR Level)
   - 期待故障：router_interface_ip_wrong
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上必须依次执行三次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip addr flush dev {iface}`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip addr add {wrong_ip} dev {iface}`
     3. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip link set {iface} up`
     其中：
     - `{iface}` 表示要篡改的三层接口名称，例如当前拓扑里的 `tos1_1`、`tos2_1`、`tor2_1`
     - `{wrong_ip}` 表示错误的接口地址，必须写成“IP/掩码”格式，例如 `10.99.99.1/24`
     - 建议把错误地址改成不属于原业务子网的地址，以确保直连网段出现明显异常
     - 在当前 `static_routing` 场景中，若对 `r1` 注入，优先选择业务侧接口 `tos1_1` 或 `tos2_1`；若对 `r2` 注入，优先选择 `tos3_1` 或 `tos4_1`
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `ip addr show {iface}`
     2. 参数 `node` 填入与该接口直连的主机名称，参数 `command` 填入 `ping -c 4 -W 2 {original_gateway_ip}`
     其中：
     - `{original_gateway_ip}` 应填写该接口修改前的原规划网关 IP，例如 `192.168.1.1`
     检测思路：若第一步显示接口地址已被改成非规划地址，且第二步直连主机无法正常访问原规划网关 IP，即可确诊路由器接口地址错误。
   - 故障表现描述：用户反馈与该路由器直连的网段全部异常，ARP 与网关解析也出现问题。

---

# **管理性关闭 BGP 邻居 (BGP Neighbor Shutdown)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：bgp_neighbor_shutdown
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "neighbor {neighbor_ip} shutdown"`。
     其中：
     - `{asn}` 表示该路由器本地 BGP 自治系统号，例如 `65001`
     - `{neighbor_ip}` 表示要被关闭的 BGP 邻居地址，一般填写与本路由器直连的对端 BGP 邻居接口 IP
     - 该命令会保留邻居配置，但将其会话强制管理性关闭
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp summary"`
     检测思路：若第一步配置中出现 `neighbor {neighbor_ip} shutdown`，且第二步显示该邻居不再处于 Established 状态，即可确诊。
   - 故障表现描述：用户反馈某节点跨域通信突然中断，邻居连接失败。

# **BGP 撤销网段宣告 (BGP Withdraw Route)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：bgp_withdraw_route
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上依次执行两次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "no network {network}"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "no redistribute connected"`
     其中：
     - `{asn}` 表示本地 AS 号，例如 `65001`
     - `{network}` 表示要撤销发布的业务网段，必须写成“网段/掩码”格式，例如 `192.168.10.0/24`
     - 如果实验拓扑本来只依赖 `network` 宣告，则第一步通常就足以造成故障；如果还开启了 `redistribute connected`，第二步也必须执行，避免该网段被继续发布
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：分别执行两步：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp summary"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     检测思路：若第一步显示 BGP 邻居仍为 Established，说明会话正常；同时第二步中目标网段对应的 `network {network}` 已消失，或 `redistribute connected` 已被撤销，即可确诊为 BGP 撤销网段宣告。
   - 故障表现描述：用户反馈邻居正常，但某远端网段突然不可达。

# **BGP 邻居 AS 号配置错误 (BGP Wrong Peer ASN)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：bgp_wrong_peer_asn
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "neighbor {neighbor_ip} remote-as {wrong_peer_asn}"`。
     其中：
     - `{asn}` 表示本地 AS 号，例如 `65001`
     - `{neighbor_ip}` 表示对端邻居地址
     - `{wrong_peer_asn}` 表示错误的对端 AS 号，建议填写一个与真实对端 AS 明显不同的值，例如 `65099`
     - 不建议使用过大且不合理的值，推荐使用实验里未被占用的正常私有 ASN
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp summary"`
     检测思路：若第一步中 `neighbor {neighbor_ip} remote-as {wrong_peer_asn}` 与真实对端不一致，且第二步状态长期停留在 `Idle`、`Active` 等非 Established 状态，即可确诊。
   - 故障表现描述：用户反馈某处 BGP 邻居始终无法建立。

# **ACL 阻断 BGP 流量 (ACL Blocking BGP Traffic)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：acl_blocking_bgp_traffic
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器。参数 `command` 填入 `iptables -I INPUT -p tcp --dport 179 -j DROP`。
     其中：
     - `179` 是 BGP 的 TCP 监听端口
     - 该规则阻断的是入站 BGP 连接请求
     - 建议注入在参与 BGP 建邻的任一端路由器上
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `iptables -L INPUT -n`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp summary"`
     检测思路：若第一步可见针对 TCP 179 的 DROP 规则，且第二步邻居状态无法进入 Established，即可确诊 ACL 阻断 BGP 流量。
   - 故障表现描述：用户反馈 BGP 会话断开后无法重连。

# **BGP Local Preference 异常升高 (BGP Local Preference Spike)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：bgp_local_pref_spike
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上必须依次执行三次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "route-map PREF permit 10" -c "set local-preference 999"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "neighbor {neighbor_ip} route-map PREF in"`
     3. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "clear ip bgp {neighbor_ip}"`
     其中：
     - `PREF` 是 route-map 名称，可自定义，建议保持简单固定
     - `10` 是 route-map 的序号，常用起始值建议填 `10`
     - `{asn}` 表示本地 AS 号，例如 `65002`
     - `{neighbor_ip}` 表示入方向应用该策略的 BGP 邻居地址
     - `999` 表示异常偏高的 local-preference，建议使用 `500`、`999` 这类远高于默认值 `100` 的数值
     - **必须执行第三步 clear**，否则已学到的旧路由属性可能不会立刻刷新，导致检测时仍看到 `localpref 100`
     - 建议选择一台有多个入方向 BGP 邻居的路由器，例如中间 AS 路由器
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议分别执行三步：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp summary"`
     3. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp {target_network}"`
     其中：
     - `{target_network}` 表示一个明确从 `{neighbor_ip}` 学到的目标前缀，例如 `192.168.2.0`
     检测思路：若第一步能看到 route-map `PREF` 已绑定到对应邻居入方向，且包含 `set local-preference 999`；第二步邻居会话恢复正常；第三步对目标前缀的详细信息中明确出现 `localpref 999`，即可确诊。**不要只看 `show ip bgp` 总表后就下结论，最好用 `show ip bgp {target_network}` 精确确认。**
   - 故障表现描述：用户反馈跨域流量突然绕行。

# **BGP MED 异常升高 (BGP MED Spike)**
   - 适用场景：simple_bgp
   - 故障类型：BGP故障 (BGP Level)
   - 期待故障：bgp_med_spike
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上必须依次执行三次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "route-map MED permit 10" -c "set metric 9999"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router bgp {asn}" -c "neighbor {neighbor_ip} route-map MED out"`
     3. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "clear ip bgp {neighbor_ip}"`
     其中：
     - `MED` 是 route-map 名称
     - `10` 是 route-map 序号，建议填 `10`
     - `{asn}` 表示本地 AS 号，例如 `65001`
     - `{neighbor_ip}` 表示出方向应用该策略的 BGP 邻居地址，例如 `192.168.0.2`
     - `9999` 表示异常偏高的 MED 数值，建议使用 `1000` 以上，常用可填 `9999`
     - **必须执行第三步 clear**，否则对端未必立即重新接收带新 MED 的更新，检测时可能仍显示旧值
     - 建议选择一个确实向外发布业务前缀的 BGP 路由器作为注入点
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议分别执行三步：
     1. 参数 `node` 填入本端路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show ip bgp {target_network}"`
     3. 可选在对端路由器执行 `vtysh -c "show ip bgp summary"`
     其中：
     - `{target_network}` 表示由本端向该邻居发布的一个业务前缀，例如 `192.168.2.0`
     检测思路：若第一步能看到 route-map `MED` 已绑定到对应邻居出方向，且包含 `set metric 9999`；第二步在对端查看该前缀时明确出现 `metric 9999`，即可确诊。**不要只看普通 `show ip bgp` 总表后立即判断，优先用 `show ip bgp {target_network}` 检查具体前缀。**
   - 故障表现描述：用户反馈对端更偏好其他入口，业务路径切换异常。

---

# **OSPF 接口静默 (OSPF Passive Interface)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_passive_interface
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 先在目标路由器执行邻居查看，参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     2. 根据邻居输出中出现的接口名，选择一个当前确实存在 OSPF 邻居的互联接口 `{interface}`
     3. 在同一路由器执行注入，参数 `command` 填入 `vtysh -c "conf t" -c "router ospf" -c "passive-interface {interface}"`
     其中：
     - `{interface}` 表示要设为静默的 OSPF 接口名称，例如 `toc2_1`、`tod1_1`
     - 必须选择一个当前正在建立邻居关系的互联接口，不要选择接用户主机或交换机的接入口
     - 配置后该接口不再发送 Hello 报文，邻居关系会逐渐消失
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface {interface}"`
     3. 可选执行：参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     检测思路：若第一步在 `router ospf` 配置下看到 `passive-interface {interface}`，且第二步接口状态中明确出现 `No Hellos (Passive interface)`，即可确诊 OSPF 接口静默已经成功注入；第三步若观察到相关邻居减少或消失，则作为增强佐证。
   - 故障表现描述：用户反馈某处原本正常的 OSPF 邻居突然断开。

# **OSPF 接口开销突增 (OSPF Cost Spike)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_cost_spike
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `vtysh -c "conf t" -c "interface {interface}" -c "ip ospf cost 65000"`。
     其中：
     - `{interface}` 表示要修改的 OSPF 接口名称，例如 `toc2_1`
     - 建议选择骨干或核心互联接口，而不是接用户侧的边缘接口
     - `65000` 表示异常偏高的链路开销，建议使用 `1000` 以上，常用可填 `65000`
     - 该故障适合诱导流量避开该链路并触发明显重收敛
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface {interface}"`
     检测思路：若配置中存在异常高的 `ip ospf cost 65000`，且接口 OSPF 信息中也能看到 `Cost: 65000`，即可确诊。
   - 故障表现描述：用户反馈流量发生大规模路径切换。

# **OSPF 进程崩溃 (OSPF Daemon Crash)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_daemon_crash
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器名称。参数 `command` 填入 `pkill ospfd`。
     其中：
     - `ospfd` 是 FRR 的 OSPF 守护进程
     - 该故障只打掉 OSPF 进程，不直接影响 `zebra` 等其他守护进程
     - 建议随机挑选一台核心 OSPF 路由器，现象更明显
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `ps aux`
     检测思路：若第一步返回 `OSPF is not running`、完全无输出或明显异常，同时第二步看不到 `ospfd` 进程，而 `zebra` 仍可能存在，则即可确诊 OSPF 进程崩溃。
   - 故障表现描述：用户反馈某路由器完全丢失所有 OSPF 路由。

# **ACL 阻断 OSPF 流量 (ACL Blocking OSPF Traffic)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：acl_blocking_ospf_traffic
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器。参数 `command` 填入 `iptables -I INPUT -p 89 -j DROP`。
     其中：
     - `89` 是 OSPF 的 IP 协议号
     - 使用协议号比写协议名称更稳妥，兼容 klonet 环境
     - 建议注入在 OSPF 邻接链路的一端
     - 注入后邻居通常不会立刻消失，需要等待一个 Dead Interval 周期
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `iptables -L INPUT -n`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     3. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface"`
     检测思路：若第一步存在协议号 89 的 DROP 规则，且经过一段时间后第二步邻居状态异常、减少或消失，同时第三步接口本身仍是 up，则即可确诊 ACL 阻断 OSPF 流量。
   - 故障表现描述：用户反馈链路物理畅通，但 OSPF 邻居持续超时消失。

# **OSPF 邻居错配 (OSPF Neighbor Misconfiguration)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_neighbor_misconfig
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器。参数 `command` 填入 `vtysh -c "conf t" -c "interface {interface}" -c "ip ospf hello-interval 99"`。
     其中：
     - `{interface}` 表示要篡改 Hello 定时器的接口名称，例如 `toc2_1`
     - `99` 表示 Hello 间隔秒数，建议使用明显偏离默认值的数值，例如 `99`
     - 必须选择一个当前与对端正在建立邻接关系的互联接口
     - 若对端仍保持默认 Hello 定时器，则两端参数不一致，邻居关系最终会异常或消失
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议分别在链路两端执行：
     1. 参数 `node` 填入第一台路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface {interface}"`
     2. 参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface {peer_interface}"`
     3. 参数 `node` 填入任意一端路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     其中：
     - `{peer_interface}` 表示对端互联接口名称
     检测思路：若两端 Hello 定时器数值不一致，例如一端为 `Hello 99s`、另一端为 `Hello 10s`，即可认定错配已经注入成功；若随后邻居状态异常、减少或消失，则更能进一步确诊。**不要强依赖邻居必须立刻掉线。**
   - 故障表现描述：用户反馈 OSPF 邻接关系始终无法建立。

# **OSPF 区域错配 (OSPF Area Misconfiguration)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_area_misconfig
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 先在目标路由器执行，参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 从 OSPF `network` 语句中选择一个当前属于骨干区域或正常区域的网段 `{network}`
     3. 在同一路由器执行注入，参数 `command` 填入 `vtysh -c "conf t" -c "router ospf" -c "network {network} area 99"`
     其中：
     - `{network}` 表示当前已由 OSPF 宣告的接口网段，格式如 `192.168.0.1/24`
     - `99` 表示错误区域号，建议使用明显不同于现网的区域，例如 `99`
     - 建议选择核心互联链路对应网段，而不是纯接入网段
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     检测思路：若第一步可见同一接口网段被错误地宣告到 `area 99`，且第二步相关邻居异常、减少或无法建立，则即可确诊 OSPF 区域错配。
   - 故障表现描述：用户反馈某些区域间路由传播异常，部分邻居无法正常建立。

# **OSPF 接口认证错配 (OSPF Auth Misconfig)**
   - 适用场景：ospf_enterprise
   - 故障类型：OSPF故障 (OSPF Level)
   - 期待故障：ospf_auth_misconfig
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上依次执行两次独立调用：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "interface {interface}" -c "ip ospf authentication message-digest"`
     2. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "interface {interface}" -c "ip ospf message-digest-key 1 md5 {wrong_key}"`
     其中：
     - `{interface}` 表示要注入认证错配的互联接口名称，例如 `toc2_1`
     - `1` 是 message-digest key-id，建议填 `1`
     - `{wrong_key}` 表示错误密钥字符串，建议填明显错误且简单固定的值，例如 `wrongkey123`
     - 建议只在一侧接口上开启认证并配置密钥，而对端保持默认不配认证，这样最容易制造错配
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     3. 可选执行：参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf neighbor"`
     4. 可选执行：参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show ip ospf interface {peer_interface}"`
     其中：
     - `{peer_interface}` 表示对端互联接口名称
     检测思路：若第一步中目标接口出现 `ip ospf authentication message-digest` 和 `ip ospf message-digest-key 1 md5 {wrong_key}`，而第二步对端对应接口未配置任何 OSPF 认证，则即可确诊 OSPF 接口认证错配已经成功注入；第三步或第四步若随后观察到邻居减少、消失或邻居计数下降到 0，则作为增强佐证。
   - 故障表现描述：用户反馈链路本身可达，但某条 OSPF 邻接关系突然无法维持。

---

# **RIP 接口静默 (RIP Passive Interface)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_passive_interface
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：建议按以下顺序执行：
     1. 先在目标路由器执行，参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 从配置中选择一个当前确实与 RIP 邻居相连的接口 `{interface}`，优先选择路由器到路由器的互联接口，而不是连接 PC 或服务器的接入口
     3. 在目标路由器执行注入，参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "passive-interface {interface}"`
     其中：
     - `{interface}` 表示要设为静默的 RIP 接口名称，例如 `tor2_1`、`tor3_1`
     - 配置后该接口不再向外发送 RIP 更新
     - 建议优先挑选一条当前确实承担 RIP 邻接和传播任务的路由器互联链路
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 可选在邻居路由器执行，参数 `node` 填入邻居路由器名称，参数 `command` 填入 `vtysh -c "show ip route"`
     检测思路：若第一步配置中已明确出现 `passive-interface {interface}`，即可判定故障注入成功；第二步若后续观察到对端逐渐失去经该接口学习到的 RIP 路由，则作为增强佐证。**不要把短时间内必须丢路由作为唯一成功标准。**
   - 故障表现描述：用户反馈邻居无法再收到本端发送的 RIP 更新。

# **RIP 路由过滤 (RIP Route Filter)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_route_filter
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上依次执行两次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "access-list 99 deny any"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "distribute-list 99 out"`
     其中：
     - `99` 是 ACL 编号，建议使用未占用的标准 ACL 号，例如 `99`
     - `deny any` 表示完全阻断该方向 RIP 路由发布
     - `out` 表示对外发出的 RIP 更新生效
     - 建议选择一台承担多个 RIP 前缀发布任务的中间路由器，以增强现象
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 可选在对端 RIP 路由器执行，参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show ip route"`
     检测思路：若第一步配置中同时出现 `access-list 99 deny any` 和 `distribute-list 99 out`，即可判定 RIP 路由过滤已成功注入；第二步若后续观察到对端失去对应 RIP 路由，则作为增强佐证。**不要把短时间内必须观察到对端丢路由作为唯一标准。**
   - 故障表现描述：用户反馈特定网段的对端学不到该路由。

# **RIP 度量值篡改 (RIP Metric Offset)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_metric_offset
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在目标路由器上依次执行两次独立调用：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "access-list 98 permit any"`
     2. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "offset-list 98 out 15"`
     其中：
     - `98` 是 ACL 编号，建议使用未占用编号
     - `permit any` 表示对所有待发布前缀应用偏移
     - `15` 是增加的 RIP 度量值，建议使用 `15`，因为 RIP 到 `16` 即视为不可达
     - `out` 表示对外发布方向生效
     - 该故障在不同拓扑中传播效果可能不完全一致，但配置注入本身是稳定的
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 可选在对端 RIP 路由器执行，参数 `node` 填入对端路由器名称，参数 `command` 填入 `vtysh -c "show ip route"`
     检测思路：若第一步配置中存在 `access-list 98 permit any` 和 `offset-list 98 out 15`，即可判定 RIP 度量值篡改已经成功注入；第二步若观察到对端不再安装该路由或路由传播异常，则作为辅助佐证。**不要仅凭短时间路由表无变化就判定注入失败。**
   - 故障表现描述：用户反馈特定 RIP 路由完全无法跨越多跳传播。

# **ACL 阻断 RIP 流量 (ACL Blocking RIP Traffic)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：acl_blocking_rip_traffic
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入路由器名称。参数 `command` 填入 `iptables -I INPUT -p udp --dport 520 -j DROP`。
     其中：
     - UDP `520` 是 RIP 的更新端口
     - `INPUT` 链表示阻断发往本机的 RIP 更新报文
     - 建议注入在一台与多个 RIP 邻居存在信息交换的路由器上
     - 注入后现有 RIP 路由不会瞬间全部消失，需要等待 RIP 老化
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入路由器名称，参数 `command` 填入 `iptables -L INPUT -n`
     2. 可选在同一路由器执行，参数 `command` 填入 `vtysh -c "show ip route"`
     检测思路：若第一步存在 UDP 520 的 DROP 规则，即可确认 ACL 阻断 RIP 流量已成功注入；第二步若后续观察到通过 RIP 学来的对端路由逐渐减少或消失，则作为增强佐证。**不要要求立即看到 RIP 路由消失。**
   - 故障表现描述：用户反馈邻居长时间学不到任何新路由宣告。

# **RIP 版本错配 (RIP Version Mismatch)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_version_mismatch
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入路由器名称。参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "version 1"`。
     其中：
     - 数字 `1` 表示将 RIP 版本强制改为 RIPv1
     - 若当前实验环境默认使用 RIPv2，则改成 `1` 能稳定制造版本错配
     - 若环境本来是 RIPv1，则应反向改成 `version 2`
     - 建议优先在处于网络边缘、但又与其他 RIP 路由器直接相连的节点上操作，这样更容易看到错配现象
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议分别在多台 RIP 路由器上执行：
     1. 参数 `node` 填入被注入路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入被注入路由器名称，参数 `command` 填入 `vtysh -c "show ip rip status"`
     3. 参数 `node` 填入相邻 RIP 路由器名称，参数 `command` 填入 `vtysh -c "show ip rip status"`
     检测思路：若被注入路由器显示 `version 1` 或状态中体现 `send version 1, receive version 1`，而相邻路由器仍为 `version 2` 或 `send version 2, receive version 2`，并伴随 `BadPackets` 增加或路由传播异常，即可确诊 RIP 版本错配。
   - 故障表现描述：用户反馈部分网段路由神秘丢失。

# **RIP 计时器篡改 (RIP Timer Misconfiguration)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_timer_misconfig
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器。参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "timers basic 999 999 999"`。
     其中：
     - 三个数字分别表示 Update、Timeout、Garbage 定时器
     - 建议填写一个非常大的值，例如 `999 999 999`
     - 该配置会让 RIP 更新和老化行为明显失真，导致极慢收敛
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show ip rip status"`
     2. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     检测思路：若状态输出中明确出现 `Sending updates every 999 seconds`、`Timeout after 999 seconds`、`garbage collect after 999 seconds`，且运行配置中也显示 `timers basic 999 999 999`，即可确诊 RIP 计时器篡改。
   - 故障表现描述：用户反馈路由收敛非常慢甚至无法收敛。

# **RIP 路由撤销 (RIP Network Withdraw)**
   - 适用场景：rip_internet
   - 故障类型：RIP故障 (RIP Level)
   - 期待故障：rip_network_withdraw
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标路由器。参数 `command` 填入 `vtysh -c "conf t" -c "router rip" -c "no network {network}"`。
     其中：
     - `{network}` 表示要从 RIP 进程中撤销发布的直连网络，格式例如 `192.168.6.1/24`
     - 建议选择当前确实由该路由器负责发布、且对端依赖该宣告学习的业务网段
     - 优先选择用户主机实际挂载的网段，这样业务现象更明显
   - 检测方法：
     使用工具：`node_execute(node, command)` 与 `ping_by_ip`
     步骤：建议分别执行：
     1. 参数 `node` 填入目标路由器名称，参数 `command` 填入 `vtysh -c "show running-config"`
     2. 参数 `node` 填入下游或对端路由器名称，参数 `command` 填入 `vtysh -c "show ip route"`
     3. 可选使用 `ping_by_ip(src_node, dst_ip)`，从远端主机探测被撤销网段内的目标主机
     检测思路：若第一步中该 `network` 已不在 `router rip` 配置下，第二步对端不再存在对应网段路由，且第三步业务探测出现 `Destination Net Unreachable` 或等价现象，即可确诊 RIP 路由撤销。
   - 故障表现描述：用户反馈原本可达的远端网段突然消失。

---

# **P4 引擎崩溃 (BMv2 Process Crash)**
   - 适用场景：p4_star
   - 故障类型：P4故障 (P4 Level)
   - 期待故障：p4_bmv2_process_crash
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入目标 P4 交换机名称。参数 `command` 填入 `pkill simple_switch`。
     其中：
     - `simple_switch` 是 BMv2 运行时核心进程名
     - 适用于直接制造 P4 数据平面整体崩溃
     - P4 交换机虽然逻辑上是 BMv2 节点，但底层仍可通过 `node_execute` 执行容器内 Linux 命令
   - 检测方法：
     使用工具：`bmv2_execute(node, cli_cmd)`
     步骤：
     1. 参数 `node` 填入交换机名称
     2. 参数 `cli_cmd` 填入 `table_dump {table_name}`
     其中：
     - `{table_name}` 建议优先填写 `MyIngress.ipv4_lpm`
     - 若不确定表名，可先调用 `find_p4_ipv4_lpm_table(node)` 获取
     检测思路：若返回 `Could not connect`、`Connection refused` 或无法连到 thrift CLI，即可确诊 BMv2 进程崩溃。
   - 故障表现描述：用户反馈途经 P4 交换机的数据流彻底中断。

# **P4 表项级 DROP 动作注入 (P4 Table Drop)**
   - 适用场景：p4_star
   - 故障类型：P4故障 (P4 Level)
   - 期待故障：p4_table_drop
   - 注入方式：
     使用工具：
     1. `find_p4_ipv4_lpm_table(node)`
     2. `get_p4_entry_handle_by_ip(switch_name, table_name, ip_with_prefix)`
     3. `bmv2_execute(node, cli_cmd)`
     步骤：
     1. 先调用 `find_p4_ipv4_lpm_table(node)` 获取实际 IPv4 LPM 转发表名 `{table_name}`
     2. 调用 `get_p4_entry_handle_by_ip`
        - 参数 `switch_name` 填入目标 P4 交换机名称
        - 参数 `table_name` 填入上一步得到的表名
        - 参数 `ip_with_prefix` 填入目标地址，建议写精确主机前缀，例如 `10.0.0.1/32`
     3. 获取纯数字 `{handle}` 后，先删除旧表项：
        - 调用 `bmv2_execute`
        - 参数 `node` 填入交换机名称
        - 参数 `cli_cmd` 填入 `table_delete {table_name} {handle}`
     4. 再重建一条 drop 表项：
        - 调用 `bmv2_execute`
        - 参数 `node` 填入交换机名称
        - 参数 `cli_cmd` 填入 `table_add {table_name} MyIngress.drop {target_ip}/32 =>`
     其中：
     - `{target_ip}` 表示不带掩码的目标 IP，例如 `10.0.0.1`
     - `{handle}` 必须先查后删，不能猜
     - `MyIngress.drop` 是目标丢弃动作名称，若程序中动作名不同，要改成实际动作名
     - **不要使用** `table_modify {table_name} MyIngress.drop {handle}`，当前 CLI 环境下该写法会报错，不能稳定成功
   - 检测方法：
     使用工具：`bmv2_execute(node, cli_cmd)` 与 `ping_by_ip(src_node, dst_ip)`
     步骤：
     1. 在交换机上执行 `table_dump {table_name}`
     2. 在源主机上执行 `ping_by_ip(src_node, dst_ip)`
     其中：
     - `{table_name}` 与注入时保持一致
     - `{dst_ip}` 为被篡改的目标主机 IP
     检测思路：若 dump 中目标 IP 对应表项动作已变成 `MyIngress.drop`，且业务 Ping 全部失败，即可确诊。
   - 故障表现描述：用户反馈某主机通往某 IP 丢包严重。

# **P4 表项级转发端口篡改 (P4 Wrong Forwarding)**
   - 适用场景：p4_star
   - 故障类型：P4故障 (P4 Level)
   - 期待故障：p4_wrong_forwarding
   - 注入方式：
     使用工具：
     1. `find_p4_ipv4_lpm_table(node)`
     2. `get_p4_entry_handle_by_ip(switch_name, table_name, ip_with_prefix)`
     3. `bmv2_execute(node, cli_cmd)`
     步骤：
     1. 先调用 `find_p4_ipv4_lpm_table(node)` 获取表名 `{table_name}`
     2. 再调用 `get_p4_entry_handle_by_ip`
        - 参数 `switch_name` 填入交换机名称
        - 参数 `table_name` 填入目标表名
        - 参数 `ip_with_prefix` 填入目标主机地址，建议填写 `10.0.0.2/32`
     3. 获取 `{handle}` 后，执行：
        - 参数 `node` 填入交换机名称
        - 参数 `cli_cmd` 填入 `table_modify {table_name} MyIngress.ipv4_forward {handle} 00:00:00:00:00:00 99`
     其中：
     - `00:00:00:00:00:00` 表示错误的下一跳目的 MAC，建议保持这个明显异常值
     - `99` 表示错误的 egress 端口号，建议填写一个明显超出交换机实际端口范围的值，如 `99`
     - 若程序动作参数顺序不同，应以实际 P4 动作为准
   - 检测方法：
     使用工具：`ping_by_ip(src_node, dst_ip)` 与 `bmv2_execute(node, cli_cmd)`
     步骤：
     1. 在源主机上执行 `ping_by_ip(src_node, dst_ip)`
     2. 在交换机上执行 `table_dump {table_name}`
     检测思路：若源主机 Ping 全部失败，同时对应表项仍是 `MyIngress.ipv4_forward`，但动作参数变成异常 MAC 与异常 egress 端口（例如 dump 中显示 `00, 63`，其中 `63` 为十六进制的 99），即可确诊。
   - 故障表现描述：用户反馈发往某个特定 IP 的数据包始终无法到达。

# **P4 表项缺失 (P4 Table Entry Missing)**
   - 适用场景：p4_star
   - 故障类型：P4故障 (P4 Level)
   - 期待故障：p4_table_entry_missing
   - 注入方式：
     使用工具：
     1. `find_p4_ipv4_lpm_table(node)`
     2. `get_p4_entry_handle_by_ip(switch_name, table_name, ip_with_prefix)`
     3. `bmv2_execute(node, cli_cmd)`
     步骤：
     1. 调用 `find_p4_ipv4_lpm_table(node)` 获取表名 `{table_name}`
     2. 调用 `get_p4_entry_handle_by_ip`
        - 参数 `switch_name` 填入交换机名称
        - 参数 `table_name` 填入目标表名
        - 参数 `ip_with_prefix` 填入目标主机 IP 或主机前缀，建议填 `10.0.0.1/32`
     3. 获取 `{handle}` 后，执行：
        - 参数 `node` 填入交换机名称
        - 参数 `cli_cmd` 填入 `table_delete {table_name} {handle}`
     其中：
     - `{handle}` 是目标表项的句柄编号，必须先通过辅助工具获取
   - 检测方法：
     使用工具：`bmv2_execute(node, cli_cmd)` 与 `ping_by_ip(src_node, dst_ip)`
     步骤：
     1. 在交换机上执行 `table_dump {table_name}`
     2. 可选在其他主机执行 `ping_by_ip(src_node, dst_ip)`
     检测思路：若 dump 输出中已找不到目标 IP 对应的匹配表项，即可确诊 P4 表项缺失；业务 Ping 失败则为增强佐证。
   - 故障表现描述：原本互通的两台主机忽然彻底无法通信。

# **P4 默认动作改为 DROP (P4 Default Action Drop)**
   - 适用场景：p4_star
   - 故障类型：P4故障 (P4 Level)
   - 期待故障：p4_default_action_drop
   - 注入方式：
     使用工具：
     1. `find_p4_ipv4_lpm_table(node)`
     2. `bmv2_execute(node, cli_cmd)`
     步骤：
     1. 先调用 `find_p4_ipv4_lpm_table(node)` 获取表名 `{table_name}`
     2. 在交换机上执行：
        - 参数 `node` 填入交换机名称
        - 参数 `cli_cmd` 填入 `table_set_default {table_name} MyIngress.drop`
     其中：
     - `{table_name}` 表示目标表名称，例如 `MyIngress.ipv4_lpm`
     - `MyIngress.drop` 表示默认丢弃动作名，如程序使用别的动作名要替换
     - 该故障主要影响未命中显式表项的流量
   - 检测方法：
     使用工具：`bmv2_execute(node, cli_cmd)`
     步骤：参数 `node` 填入交换机名称，参数 `cli_cmd` 填入 `table_dump {table_name}`
     检测思路：若表的默认动作已被设置为 `MyIngress.drop`，即 dump 中 `Dumping default entry` 下显示 `Action entry: MyIngress.drop -`，即可确诊。
   - 故障表现描述：新出现或未显式配置的流量全部无法通过交换机。

---

# **Ryu 控制器崩溃 (SDN Controller Crash)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：sdn_controller_crash
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：在 SDN 控制器节点上必须分两次独立执行：
     1. 参数 `node` 填入控制器节点名称，参数 `command` 填入 `pkill ryu-manager`
     2. 参数 `node` 填入控制器节点名称，参数 `command` 填入 `pkill python`
     其中：
     - 第一条针对直接以 `ryu-manager` 名称运行的进程
     - 第二条用于兜底清理可能承载 Ryu 的 Python 进程
     - 由于第二条可能影响控制器上其他 Python 服务，使用时需确认节点角色单一
   - 检测方法：
     使用工具：`node_execute(node, command)` 与 `get_reachability()`
     步骤：建议依次执行：
     1. 参数 `node` 填入控制器节点名称，参数 `command` 填入 `ss -tln`
     2. 参数 `node` 填入控制器节点名称，参数 `command` 填入 `ps aux`
     3. 可选调用 `get_reachability()`
     检测思路：若 `ss -tln` 中看不到 `6653` 或 `6633` 监听端口，同时 `ps aux` 中无 Ryu 相关进程，即可确诊控制器崩溃；若 `get_reachability()` 同时显示主机间互通失败、控制面探测异常，则为增强佐证。
   - 故障表现描述：用户反馈 SDN 网络失去控制，新上的主机无法通信。

# **OVS 断开控制器连接 (OVS Disconnect)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：ovs_disconnect
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：必须拆分执行：
     1. 调用 `ovs_list_bridges(node)` 获取实际 bridge 名称
     2. 从输出中选择目标 bridge，记为 `{bridge_name}`
     3. 参数 `node` 填入同一交换机名称，参数 `command` 填入 `ovs-vsctl del-controller {bridge_name}`
     其中：
     - `{bridge_name}` 表示 OVS 网桥名称，常见如 `init-br0`
     - 若交换机上存在多个桥，应逐个独立执行删除控制器命令
     - 不允许使用 shell 循环或命令替换来批量处理
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入交换机名称，参数 `command` 填入 `ovs-vsctl show`
     2. 参数 `node` 填入控制器名称，参数 `command` 填入 `ss -tln`
     检测思路：若控制器端口仍在监听，但交换机 `ovs-vsctl show` 中已不再绑定 controller，或不再显示连接状态，即可确诊 OVS 断开控制器连接。
   - 故障表现描述：用户反馈某台交换机似乎失控。

# **OVS 注入全局 DROP 流表 (OVS Global Drop)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：ovs_global_drop
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：必须拆分执行：
     1. 调用 `ovs_list_bridges(node)` 获取网桥名
     2. 从输出中选择目标网桥 `{bridge_name}`
     3. 参数 `node` 填入交换机名称，参数 `command` 填入 `ovs-ofctl add-flow {bridge_name} priority=65535,actions=drop`
     其中：
     - `{bridge_name}` 表示要注入规则的 OVS 网桥
     - `65535` 是极高优先级，建议保持该值以确保覆盖其他普通流表
     - `actions=drop` 表示直接丢弃匹配流量；由于未加匹配字段，实际为全局兜底丢弃
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：
     1. 参数 `node` 填入交换机名称，参数 `command` 填入 `ovs-ofctl dump-flows {bridge_name}`
     2. 可选在相关主机执行 `ping -c 4 -W 2 {target_ip}`
     检测思路：若存在高优先级 `priority=65535` 且 `actions=drop` 的流表项，即可确诊 OVS 全局 DROP 流表故障；若业务同时出现全阻断，则为增强佐证。
   - 故障表现描述：用户反馈途经某台交换机的所有流量都被无差别丢弃。

# **南向控制器地址错配 (Southbound Wrong Controller Address)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：southbound_wrong_controller
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：必须拆分执行：
     1. 调用 `ovs_list_bridges(node)` 获取 bridge 名称
     2. 从输出中选择目标网桥 `{bridge_name}`
     3. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-vsctl set-controller {bridge_name} tcp:192.168.254.254:6653`
     其中：
     - `{bridge_name}` 表示目标 OVS 网桥名称
     - `192.168.254.254` 是一个明显错误且通常不可达的控制器地址，建议保持此类未使用地址
     - `6653` 是 OpenFlow 常用南向端口
     - 该故障本质上也是南向控制面断连，但不依赖 controller 容器是否有 iptables
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：
     1. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-vsctl show`
     2. 参数 `node` 填入控制器名称，参数 `command` 填入 `ss -tln`
     检测思路：若控制器端口仍在监听，但 OVS 侧 controller 地址已变成错误地址，且连接状态异常或不再连接，即可确诊南向控制器地址错配。
   - 故障表现描述：用户反馈交换机仍在运行，但始终无法与控制器建立控制连接。

# **南向接口协议错配 (Southbound Protocol Mismatch)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：southbound_protocol_mismatch
   - 注入方式：
     使用工具：`ovs_list_bridges(node)`、`ovs_get_bridge_protocols(node, bridge_name)` 与 `node_execute(node, command)`
     步骤：建议依次执行：
     1. 调用 `ovs_list_bridges(node)` 获取目标 OVS 的 bridge 名称 `{bridge_name}`
     2. 参数 `node` 填入 OVS 节点，参数 `command` 填入 `ovs-vsctl set bridge {bridge_name} protocols=OpenFlow10`
     其中：
     - `{bridge_name}` 表示目标 OVS 网桥名称
     - `OpenFlow10` 表示强行降级协议版本
     - 若当前控制器要求 OpenFlow13 或更高版本，该故障能稳定制造协议错配
   - 检测方法：
     使用工具：`ovs_get_bridge_protocols(node, bridge_name)` 与 `node_execute(node, command)`
     步骤：建议依次执行：
     1. 调用 `ovs_get_bridge_protocols(node, bridge_name)` 检查协议版本
     2. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-vsctl show`
     检测思路：若 bridge 的 `protocols` 字段为 `OpenFlow10`，且控制器连接状态异常或策略无法下发，即可确诊南向协议错配。
   - 故障表现描述：控制器提示报文格式无法识别。

# **流表规则覆盖 (Flow Rule Shadowing)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：flow_rule_shadowing
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：
     1. 调用 `ovs_list_bridges(node)` 获取目标网桥 `{bridge_name}`
     2. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-ofctl add-flow {bridge_name} priority=1000,actions=normal`
     其中：
     - `{bridge_name}` 表示 OVS 网桥名称
     - `priority=1000` 表示注入一条比普通学习规则更高的通配规则
     - `actions=normal` 会把业务退化为普通二层交换逻辑，从而覆盖控制器原有细粒度策略
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：
     1. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-ofctl dump-flows {bridge_name}`
     检测思路：若流表中存在 `priority=1000 actions=normal` 的宽泛高优先级规则，即可确诊流表规则覆盖。
   - 故障表现描述：用户反馈业务流量不再按控制器预期路径转发。

# **流表环路注入 (Flow Rule Loop)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：flow_rule_loop
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：
     1. 调用 `ovs_list_bridges(node)` 获取目标网桥 `{bridge_name}`
     2. 参数 `node` 填入 OVS 节点，参数 `command` 填入 `ovs-ofctl add-flow {bridge_name} priority=2000,in_port=1,actions=output:1`
     其中：
     - `{bridge_name}` 表示 OVS 网桥名称
     - `priority=2000` 表示高优先级，建议保持 `2000` 或更高
     - `in_port=1` 表示匹配从 1 号端口进入的流量
     - `actions=output:1` 表示又从 1 号端口发回，形成自回环
     - 注入前应确认 1 号端口真实存在
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：
     1. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-ofctl dump-flows {bridge_name}`
     2. 参数 `node` 填入相关主机名称，参数 `command` 填入 `ping -c 4 -W 2 {target_ip}`
     检测思路：若流表中存在 `in_port=1,actions=output:1` 的高优先级规则，且业务出现异常丢包、不可达或环路现象，即可确诊。
   - 故障表现描述：网络似乎卡死。

# **OVS 本地桥转发关闭 (OVS Fail Mode Secure)**
   - 适用场景：sdn_openflow
   - 故障类型：SDN故障 (SDN Level)
   - 期待故障：ovs_fail_secure
   - 注入方式：
     使用工具：`ovs_list_bridges(node)` 与 `node_execute(node, command)`
     步骤：
     1. 调用 `ovs_list_bridges(node)` 获取目标网桥 `{bridge_name}`
     2. 参数 `node` 填入 OVS 节点，参数 `command` 填入 `ovs-vsctl set-fail-mode {bridge_name} secure`
     其中：
     - `{bridge_name}` 表示目标网桥名称
     - `secure` 表示在控制器失联时，交换机不进行普通 fallback 转发
     - 该故障最好与控制器失联类现象组合观察，效果更明显
   - 检测方法：
     使用工具：`node_execute(node, command)`
     步骤：建议依次执行：
     1. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-vsctl show`
     2. 参数 `node` 填入 OVS 节点名称，参数 `command` 填入 `ovs-vsctl list bridge`
     检测思路：若桥的 `fail_mode` 已变为 `secure`，即可确认故障注入成功；若后续控制器异常时业务中断，则作为增强佐证。
   - 故障表现描述：控制器短暂异常后，交换机不再转发。

---

# **AI 推理进程崩溃 (AI Service Crash)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：ai_service_crash
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入算力节点名称，参数 `command` 填入 `pkill python3`。
     其中：
     - 当前 ai_inference 场景中的真实推理服务通过 `python3 /tmp/real_llm.py` 启动
     - 因此直接终止 `python3` 进程即可稳定制造 AI 推理进程崩溃故障
   - 检测方法：
     使用工具：`test_ai_inference` 与 `node_execute`
     步骤：
     1. 调用 `test_ai_inference(client_node, server_ip, port)`，其中 `port` 一般填 `8000`
     2. 在服务端执行 `ss -tln`
     3. 可选在服务端执行 `ps aux`
     检测思路：若 `test_ai_inference` 返回连接失败、连接拒绝或超时，同时 `ss -tln` 中看不到 `8000` 监听端口，即可确诊 AI 推理进程崩溃。
   - 故障表现描述：用户反馈 AI 助手突然不再回复任何消息。

# **算力节点 CPU 满载 (Compute CPU Starvation)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：compute_cpu_starvation
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入算力节点名称。参数 `command` 填入 `stress-ng --cpu 4 --timeout 300s`。
     其中：
     - `--cpu 4` 表示启动 4 个 CPU 压力 worker，建议根据节点核数选择，一般填 `2` 或 `4`
     - `--timeout 300s` 表示持续 300 秒，建议默认填 `300s`
     - 该命令在平台上可能返回 504 或超时，但只要后续进程和资源占用检测显示 `stress-ng` 已运行，就应视为注入成功
   - 检测方法：
     使用工具：`check_ai_processes`、`node_execute(node, command)` 与 `test_ai_inference`
     步骤：
     1. 参数 `node` 填入算力节点名称，调用 `check_ai_processes(node)` 检查是否存在 `stress-ng` 与 `stress-ng-cpu` 进程
     2. 参数 `node` 填入算力节点名称，参数 `command` 填入 `top -b -n 1`
     3. 调用 `test_ai_inference(client_node, server_ip, port)` 检查业务响应时间
     检测思路：若进程列表中存在 `stress-ng` 及多个 `stress-ng-cpu` worker，且 `top` 中对应进程持续高占用 CPU，同时 AI 推理请求耗时显著上升或返回异常，即可确诊算力节点 CPU 满载。**不要把注入命令返回 504 直接判定为失败。**
   - 故障表现描述：用户反馈 AI 吐字极度缓慢。

# **算力节点内存溢出 (Compute Memory Exhaustion)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：compute_memory_exhaustion
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入算力节点名称。参数 `command` 填入 `stress-ng --vm 1 --vm-bytes 95% --vm-hang 300 --timeout 300s`。
     其中：
     - `--vm 1` 表示启动 1 个内存压力 worker，建议填 `1`
     - `--vm-bytes 95%` 表示占用约 95% 的可用内存，建议填 `90%` 或 `95%`
     - `--vm-hang 300` 表示 worker 在分配后保持 300 秒，建议与总超时时间保持一致
     - `--timeout 300s` 表示总持续时间 300 秒
     - 该命令在平台上可能返回 504 或超时，但只要后续进程和资源占用检测显示 `stress-ng` 已运行，就应视为注入成功
   - 检测方法：
     使用工具：`check_ai_processes`、`node_execute(node, command)` 与 `test_ai_inference`
     步骤：
     1. 参数 `node` 填入算力节点名称，调用 `check_ai_processes(node)` 检查是否存在 `stress-ng` 与 `stress-ng-vm` 进程
     2. 参数 `node` 填入算力节点名称，参数 `command` 填入 `free -m`
     3. 参数 `node` 填入算力节点名称，参数 `command` 填入 `top -b -n 1`
     4. 调用 `test_ai_inference(client_node, server_ip, port)`
     检测思路：若进程列表中存在 `stress-ng` 与 `stress-ng-vm`，且 `free -m` 显示 available 内存明显下降、`top` 中 `stress-ng-vm` 占用内存显著上升，同时 AI 推理业务返回异常、失败或超时，即可确诊算力节点内存溢出。**不要把注入命令返回 504 直接判定为失败。**
   - 故障表现描述：用户反馈大并发请求时，AI 服务突然无响应。

# **推理端口防火墙阻断 (Inference Port Blocked)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：inference_port_blocked
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入算力节点名称。参数 `command` 填入 `iptables -I INPUT -p tcp --dport 8000 -j DROP`。
     其中：
     - `8000` 是 AI 推理 HTTP 服务的默认监听端口，建议一般填 `8000`
     - 若你的服务监听在其他端口，需替换成实际端口
     - 该规则只影响应用层 TCP 访问，不影响 ICMP 测试
   - 检测方法：
     使用工具：`test_ai_inference`、`node_execute` 与 `ping_by_ip`
     步骤：
     1. 调用 `test_ai_inference(client_node, server_ip, port)`，其中 `port` 一般填 `8000`
     2. 参数 `node` 填入算力节点名称，参数 `command` 填入 `iptables -L INPUT -n`
     3. 调用 `ping_by_ip(src_node, dst_ip)` 验证底层网络仍连通
     检测思路：若底层 Ping 正常，但 `test_ai_inference` 请求超时或失败，同时服务端 INPUT 链存在针对 `8000` 的 DROP 规则，即可确诊推理端口防火墙阻断。
   - 故障表现描述：用户反馈能 Ping 通服务器，但推理 API 全部超时。

# **TCP RST 注入 (TCP RST Injection)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：tcp_rst_injection
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入中间转发节点名称。参数 `command` 填入 `iptables -I FORWARD -p tcp -j REJECT --reject-with tcp-reset`。
     其中：
     - `FORWARD` 表示拦截经过该节点转发的 TCP 流量
     - `REJECT --reject-with tcp-reset` 表示直接向会话两端返回 TCP RST，制造连接被重置
     - 该命令比 `DROP` 更适合模拟“连接建立或传输过程中被立即 reset”的现象
   - 检测方法：
     使用工具：`node_execute(node, command)`、`ping_by_ip(src_node, dst_ip)` 与 `test_ai_inference`
     步骤：
     1. 在中间节点，参数 `node` 填入中间转发节点名称，参数 `command` 填入 `iptables -L FORWARD -n`
     2. 调用 `ping_by_ip(src_node, dst_ip)`，验证客户端到服务端底层 ICMP 正常
     3. 调用 `test_ai_inference(client_node, server_ip, port)`，其中 `port` 一般填 `8000`
     检测思路：若中间节点存在 `reject-with tcp-reset` 规则，且客户端到服务端底层 ICMP 正常，同时 AI 推理请求表现为异常失败或连接被中途重置，即可确诊 TCP RST 注入。
   - 故障表现描述：用户反馈连接建立后很快被异常重置。

# **算网隔离 / 跨层路由黑洞 (Cross-Layer Traffic Blackhole)**
   - 适用场景：ai_inference
   - 故障类型：AI推理故障 (AI Inference Level)
   - 期待故障：cross_layer_traffic_blackhole
   - 注入方式：
     使用工具：`node_execute(node, command)`
     步骤：参数 `node` 填入连接 server 的接入路由或中间转发节点名称。参数 `command` 填入 `iptables -I FORWARD -d {server_ip} -p tcp --dport 8000 -j DROP`。
     其中：
     - `{server_ip}` 表示 AI 推理服务器 IP
     - `8000` 是默认 AI HTTP 服务端口，建议一般填 `8000`
     - `FORWARD` 表示只影响经过该中间节点转发的业务流
     - `DROP` 表示静默丢弃，更适合模拟跨层黑洞或路径黑洞
   - 检测方法：
     使用工具：`node_execute(node, command)`、`test_ai_inference` 与 `ping_by_ip`
     步骤：
     1. 在客户端调用 `test_ai_inference(client_node, server_ip, port)`
     2. 在中间节点执行 `iptables -L FORWARD -n`
     3. 可选在客户端执行 `ping_by_ip(src_node, dst_ip)`
     检测思路：若客户端到服务端底层 Ping 正常或基本正常，但 AI 推理业务持续超时，同时中间节点 FORWARD 链存在针对 `{server_ip}:8000` 的 DROP 规则，即可确诊算网隔离或跨层路由黑洞。
   - 故障表现描述：用户反馈跨机房请求算力节点时业务大包被神秘丢弃。