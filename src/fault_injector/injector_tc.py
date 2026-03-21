import re
import time
from service.klonet import KlonetTCAPI
import logging
system_logger = logging.getLogger("PlayGround")

class LinkFaultInjector:
    """
    链路层故障注入器 (基于 Linux TC NetEm)
    涵盖：高延迟、丢包、抖动、乱序、带宽限制
    """
    def __init__(self, lab_name: str):
        self.lab_name = lab_name
        self.api = KlonetTCAPI(lab_name)
        self.logger = system_logger

    # --- 1. 高延迟故障 ---
    def inject_link_latency(self, host_name: str, link_name: str, delay_ms: int = 500, jitter_ms: int = 0):
        """
        [注入] 链路高延迟
        输入: host_name, link_name(拓扑中的链路ID, 如l1), delay_ms(延迟), jitter_ms(抖动)
        """
        self.logger.info(f"正在注入故障: {host_name} 链路 {link_name} 增加延迟 {delay_ms}ms (抖动 {jitter_ms}ms)")
        self.api.tc_set_netem(
            host_name=host_name,
            link=link_name,
            delay_ms=delay_ms,
            jitter_ms=jitter_ms
        )

    # --- 2. 链路丢包 ---
    def inject_link_loss(self, host_name: str, link_name: str, loss_percent: int = 20):
        """
        [注入] 链路高丢包
        输入: host_name, link_name, loss_percent(丢包率 %)
        """
        self.logger.info(f"正在注入故障: {host_name} 链路 {link_name} 丢包率 {loss_percent}%")
        self.api.tc_set_netem(
            host_name=host_name,
            link=link_name,
            loss=loss_percent
        )

    # --- 3. 链路抖动 (Jitter) ---
    def inject_link_jitter(self, host_name: str, link_name: str, delay_ms: int = 100, jitter_ms: int = 80):
        """
        [注入] 链路高抖动 (通常伴随延迟)
        输入: host_name, link_name, delay_ms(基础延迟), jitter_ms(抖动幅度)
        """
        self.logger.info(f"正在注入故障: {host_name} 链路 {link_name} 高抖动 {jitter_ms}ms")
        self.api.tc_set_netem(
            host_name=host_name,
            link=link_name,
            delay_ms=delay_ms,
            jitter_ms=jitter_ms,
            delay_distribution="normal" # 正态分布抖动
        )

    # --- 4. 带宽限制 ---
    def inject_link_bandwidth(self, host_name: str, link_name: str, bw_kbps: int = 1):
        """
        [注入] 带宽限制 (Throttling)
        输入: host_name, link_name, bw_kbps(带宽上限 kbps)
        """
        self.logger.info(f"正在注入故障: {host_name} 链路 {link_name} 限制带宽 {bw_kbps}kbps")
        self.api.tc_set_netem(
            host_name=host_name,
            link=link_name,
            bw_kbps=bw_kbps
        )

    # --- 通用恢复 ---
    def recover_link_fault(self, host_name: str, link_name: str):
        """
        [恢复] 清除链路的所有 TC 规则
        输入: host_name, link_name (注意 Klonet 底层可能只需要 link_name，但也可能需要 host 定位)
        """
        self.logger.info(f"正在恢复: 清除 {host_name} 链路 {link_name} 的 TC 规则")
        # 根据 tc_api.py，tc_clear_netem 只需要 link_name，但在逻辑上我们通常关联到 host
        self.api.tc_clear_netem(link_name)
