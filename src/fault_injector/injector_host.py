import time
from service.klonet import KlonetIptablesAPI
import logging
system_logger = logging.getLogger("PlayGround")

class HostFaultInjector:
    """
    主机层故障注入器
    涵盖：IP/路由配置错误、ARP欺骗、接口Down、资源过载等
    """
    def __init__(self, lab_name: str):
        self.lab_name = lab_name
        # 使用 IptablesAPI，因为它封装了 iproute2 和基础 linux 命令
        self.api = KlonetIptablesAPI(lab_name)
        self.logger = system_logger

    # --- 1. IP 配置故障 ---
    def inject_ip_misconfig(self, host_name: str, iface: str, wrong_ip: str):
        """
        [注入] IP地址配置错误：将接口 IP 修改为错误网段或冲突 IP
        输入: host_name(主机名), iface(接口名), wrong_ip(错误IP/掩码), original_ip(用于日志记录的原IP)
        """
        self.logger.info(f"正在注入故障: 修改 {host_name}:{iface} IP 为 {wrong_ip}")
        # 先删后加
        self.api._run_cmd(host_name, f"ip addr flush dev {iface}")
        self.api._run_cmd(host_name, f"ip addr add {wrong_ip} dev {iface}")
        self.api._run_cmd(host_name, f"ip link set {iface} up")

    # --- 2. 路由配置故障 ---
    def inject_default_route_missing(self, host_name: str):
        """
        [注入] 默认路由缺失：删除 default gateway
        输入: host_name
        """
        self.logger.info(f"正在注入故障: 删除 {host_name} 默认路由")
        self.api._run_cmd(host_name, "ip route del default")

    # --- 3. ARP/MAC 故障 ---
    def inject_arp_poisoning(self, host_name: str, target_ip: str, fake_mac: str = "aa:bb:cc:dd:ee:ff"):
        """
        [注入] ARP 缓存投毒：将目标 IP 静态绑定到错误 MAC
        输入: host_name, target_ip(受害者IP), fake_mac(欺骗MAC)
        """
        self.logger.info(f"正在注入故障: {host_name} ARP投毒 {target_ip} -> {fake_mac}")
        self.api._run_cmd(host_name, f"arp -s {target_ip} {fake_mac}")

    # --- 4. 物理/接口层故障 ---
    def inject_interface_down(self, host_name: str, iface: str):
        """
        [注入] 接口 Down：模拟网线断开或网卡关闭
        输入: host_name, iface
        """
        self.logger.info(f"正在注入故障: 关闭接口 {host_name}:{iface}")
        self.api.linux_set_link_status(host_name, iface, "down")

    # --- 5. DNS 配置故障 ---
    def inject_dns_error(self, host_name: str, fake_dns: str = "0.1.2.3"):
        """
        [注入] DNS 配置错误：修改 DNS 服务器为错误地址
        输入: host_name, fake_dns(错误DNS)
        """
        self.logger.info(f"正在注入故障: 修改 {host_name} DNS 为 {fake_dns}")
        # [修复] 必须用 sh -c 将命令包裹，强制启动 shell 解释器来处理重定向符号 '>'
        self.api._run_cmd(host_name, f'sh -c "echo nameserver {fake_dns} > /etc/resolv.conf"')

    # --- 6. 资源过载故障 ---
    def inject_high_cpu_load(self, host_name: str, duration: int = 300):
        """
        [注入] CPU 满载：在主机上制造高 CPU 负载持续一段时间
        输入: host_name, duration(持续时间)
        """
        self.logger.info(f"正在注入故障: {host_name} CPU 满载持续 {duration}s")
        # [修复] 放弃 stress-ng，使用原生 dd 命令死循环读取 /dev/zero 制造 100% CPU 占用
        # 启动两个后台进程以应对多核情况
        self.api._run_cmd(host_name, "nohup sh -c 'dd if=/dev/zero of=/dev/null' > /dev/null 2>&1 &")
        self.api._run_cmd(host_name, "nohup sh -c 'dd if=/dev/zero of=/dev/null' > /dev/null 2>&1 &")
