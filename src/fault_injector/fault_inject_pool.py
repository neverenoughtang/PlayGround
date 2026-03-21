import time
import sys
import subprocess
# 同级目录下的文件，必须加一个点 '.' 表示明确的相对导入
from .injector_host import HostFaultInjector
from .injector_service import ServiceFaultInjector
from .injector_tc import LinkFaultInjector
from .lab_injector_input import HOST_INJECT_INPUT, LINK_INJECT_INPUT, SERVICE_INJECT_INPUT


# =====================================================================
# 故障调度引擎
# =====================================================================
class FaultInjector:
    """综合故障注入调度池 (组合设计模式)"""
    def __init__(self, lab_name: str):
        self.lab_name = lab_name
        self.host_inj = HostFaultInjector(lab_name)
        self.service_inj = ServiceFaultInjector(lab_name)
        self.link_inj = LinkFaultInjector(lab_name)

        # 路由表
        self.FAULT_MAP = {
            "inject_ip_misconfig": ("host", self.host_inj.inject_ip_misconfig),
            "inject_default_route_missing": ("host", self.host_inj.inject_default_route_missing),
            "inject_arp_poisoning": ("host", self.host_inj.inject_arp_poisoning),
            "inject_interface_down": ("host", self.host_inj.inject_interface_down),
            "inject_dns_error": ("host", self.host_inj.inject_dns_error),
            "inject_high_cpu_load": ("host", self.host_inj.inject_high_cpu_load),
            
            "inject_link_latency": ("link", self.link_inj.inject_link_latency),
            "inject_link_loss": ("link", self.link_inj.inject_link_loss),
            "inject_link_jitter": ("link", self.link_inj.inject_link_jitter),
            "inject_link_bandwidth": ("link", self.link_inj.inject_link_bandwidth),
            
            "inject_route_missing": ("service", self.service_inj.inject_route_missing),
            "inject_static_route_blackhole": ("service", self.service_inj.inject_static_route_blackhole),
            "inject_router_data_plane_drop": ("service", self.service_inj.inject_router_data_plane_drop),
            
            "inject_bgp_neighbor_shutdown": ("service", self.service_inj.inject_bgp_neighbor_shutdown),
            "inject_bgp_withdraw_route": ("service", self.service_inj.inject_bgp_withdraw_route),
            "inject_bgp_wrong_peer_asn": ("service", self.service_inj.inject_bgp_wrong_peer_asn),
            
            "inject_ospf_passive_interface": ("service", self.service_inj.inject_ospf_passive_interface),
            "inject_ospf_cost_spike": ("service", self.service_inj.inject_ospf_cost_spike),
            "inject_ospf_daemon_crash": ("service", self.service_inj.inject_ospf_daemon_crash),
            
            "inject_rip_route_filter": ("service", self.service_inj.inject_rip_route_filter),
            "inject_rip_passive_interface": ("service", self.service_inj.inject_rip_passive_interface),
            "inject_rip_metric_offset": ("service", self.service_inj.inject_rip_metric_offset),
            
            "inject_sdn_controller_crash": ("service", self.service_inj.inject_sdn_controller_crash),
            "inject_ovs_disconnect_controller": ("service", self.service_inj.inject_ovs_disconnect_controller),
            "inject_ovs_global_drop_flow": ("service", self.service_inj.inject_ovs_global_drop_flow),
            
            "inject_bmv2_process_crash": ("service", self.service_inj.inject_bmv2_process_crash),
            "inject_p4_table_drop": ("service", self.service_inj.inject_p4_table_drop),
            "inject_p4_wrong_forwarding": ("service", self.service_inj.inject_p4_wrong_forwarding)
        }

    def inject(self, fault_name: str):
        """统一执行注入"""
        if fault_name not in self.FAULT_MAP:
            print(f"❌ Error: Invalid fault name '{fault_name}'")
            return

        category, func = self.FAULT_MAP[fault_name]
        print(f"[System] 正在为 {self.lab_name} 下发 {category.upper()} 故障: {fault_name}")

        try:
            if category == "host":
                cfg = HOST_INJECT_INPUT[self.lab_name]
                if fault_name == "inject_ip_misconfig": func(cfg["target"], cfg["iface"], cfg["wrong_ip"])
                elif fault_name == "inject_default_route_missing": func(cfg["target"])
                elif fault_name == "inject_arp_poisoning": func(cfg["target"], cfg["target_ip"], cfg["wrong_mac"])
                elif fault_name == "inject_interface_down": func(cfg["target"], cfg["iface"])
                elif fault_name == "inject_dns_error": func(cfg["target"])
                elif fault_name == "inject_high_cpu_load": func(cfg["target"])
            elif category == "link":
                cfg = LINK_INJECT_INPUT[self.lab_name]
                if fault_name == "inject_link_latency": func(cfg["host"], cfg["link_id"], delay_ms=500, jitter_ms=0)
                elif fault_name == "inject_link_loss": func(cfg["host"], cfg["link_id"], loss_percent=50)
                elif fault_name == "inject_link_jitter": func(cfg["host"], cfg["link_id"], delay_ms=100, jitter_ms=80)
                elif fault_name == "inject_link_bandwidth": func(cfg["host"], cfg["link_id"], bw_kbps=1000)
            elif category == "service":
                cfg = SERVICE_INJECT_INPUT.get(self.lab_name)
                if not cfg: raise ValueError(f"缺少 {self.lab_name} 的 SERVICE 配置字典")
                # [完全对齐字典键名]
                if fault_name in ["inject_route_missing", "inject_static_route_blackhole"]: 
                    func(cfg["router"], cfg["blackhole_net"])
                elif fault_name in ["inject_router_data_plane_drop", "inject_ospf_daemon_crash", "inject_rip_metric_offset", "inject_rip_route_filter"]: 
                    func(cfg["router"])
                elif fault_name == "inject_bgp_neighbor_shutdown": 
                    func(cfg["router"], cfg["asn"], cfg["neighbor_ip"])
                elif fault_name == "inject_bgp_withdraw_route": 
                    func(cfg["router"], cfg["asn"], cfg["withdraw_net"])  # [修复] 改为 withdraw_net
                elif fault_name == "inject_bgp_wrong_peer_asn": 
                    func(cfg["router"], cfg["asn"], cfg["neighbor_ip"], cfg["wrong_asn"])
                elif fault_name in ["inject_ospf_passive_interface", "inject_ospf_cost_spike"]: 
                    func(cfg["router"], cfg["passive_iface"])
                elif fault_name == "inject_rip_passive_interface": 
                    func(cfg["router"], cfg["passive_iface"])
                elif fault_name == "inject_sdn_controller_crash": 
                    func(cfg["controller"])
                elif fault_name in ["inject_ovs_disconnect_controller", "inject_ovs_global_drop_flow"]: 
                    func(cfg["switch"])
                elif fault_name == "inject_bmv2_process_crash": 
                    func(cfg["switch"])
                elif fault_name == "inject_p4_table_drop": 
                    func(cfg["switch"], cfg["table"], cfg["drop_ip"])      # [修复] 改为 drop_ip
                elif fault_name == "inject_p4_wrong_forwarding": 
                    func(cfg["switch"], cfg["table"], cfg["drop_ip"], cfg["wrong_port"])  # [修复] 改为 drop_ip
        except Exception as e:
            print(f"[System] ❌ 注入失败 Error: {e}")
