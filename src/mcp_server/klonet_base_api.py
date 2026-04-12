import asyncio
import json
import os
from typing import Dict, List, Optional

from KlonetAPI import Klonet


# 简化拓扑函数
def simplify_topo(lab_name: str, raw_topo: dict) -> str:
    """
    接收全量的拓扑 JSON 字典，过滤掉所有非网络特性的冗余参数，
    仅保留节点(名称/类型/接口/IP/网关)和链路(源/目的及对应IP)。
    """
    simplified = []
    simplified.append(f"\n {lab_name} 的拓扑信息:")
    
    # 1. 提炼节点信息
    simplified.append("\n[节点列表]")
    categories = ['controllers', 'hosts', 'routers', 'switches', 'dpdks']
    for category in categories:
        if category not in raw_topo or not raw_topo[category]:
            continue
            
        for node_name, node_info in raw_topo[category].items():
            # 基础网络属性
            node_type = node_info.get('type', category)
            gateway = node_info.get('gateway', '')
            interfaces = node_info.get('interfaces', [])
            
            # 格式化接口
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')
                netmask = iface.get('netmask', '/24') 
                mask = f"/{sum(bin(int(x)).count('1') for x in netmask.split('.'))}" # 掩码

                # 修正接口名称：如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname

                if ip:
                    iface_strs.append(f"{actual_iname}({ip}{mask})")
                else:
                    iface_strs.append(f"{actual_iname}")
            
            # 拼接单节点信息
            info_str = f"- {node_name} [{node_type}]"
            if iface_strs:
                info_str += f" | 接口: {', '.join(iface_strs)}"
            if gateway:
                info_str += f" | 默认网关: {gateway}"
                
            simplified.append(info_str)
            
    # 2. 提炼链路信息
    simplified.append("\n[链路]")
    links = raw_topo.get('links', {})
    for link_name, link_info in links.items():
        src = link_info.get('source', '')
        src_ip = link_info.get('sourceIP', '')
        tgt = link_info.get('target', '')
        tgt_ip = link_info.get('targetIP', '')
        
        # 移除掩码后缀(如 /24)，保持视觉清爽
        src_ip_clean = src_ip.split('/')[0] if src_ip else ""
        tgt_ip_clean = tgt_ip.split('/')[0] if tgt_ip else ""
        
        src_str = f"{src}({src_ip_clean})" if src_ip_clean else src
        tgt_str = f"{tgt}({tgt_ip_clean})" if tgt_ip_clean else tgt
        
        simplified.append(f"- 链路 {link_name}: {src_str} <---> {tgt_str}")
        
    return "\n".join(simplified)


class KlonetBaseAPI:
    """
    深度优化版 Base API
    """

    def __init__(self, lab_name: str):
        self.lab = Klonet()
        self.lab.klonet_login(
            project_name=lab_name,
            user_name=os.getenv("USER_NAME"),
            host_ip=os.getenv("BACKEND_IP"),
            port=os.getenv("BACKEND_PORT"),
        )
        if not self.lab.test_klonet_connection():
            raise ValueError(f"无法连接到 Klonet 后端或项目 {lab_name}!")

    def destroy(self):
        """
        销毁项目
        """
        self.lab.reset_project()


    def _run_cmd(self, node_name: str, command: str, timeout: int = 60) -> str:
        """
        同步执行命令（基于 Klonet block="true"）
        已内置异常捕获和超时处理
        """
        try:
            response = self.lab.execute(node_name, command, block="true", timeout=timeout)
            if not isinstance(response, dict):
                return str(response).strip() # 对于非字典响应的备用处理

            node_res = response.get(node_name, {})
            if not node_res:
                return f"[ERROR] {node_name} 命令执行无响应。"

            # 寻找实际的命令键，该键可能以索引（如 "0_"）为前缀
            # 我们查找以我们传入的 `command` 字符串结尾的键
            actual_cmd_key = next((k for k in node_res if k.endswith(command)), None)

            if actual_cmd_key:
                cmd_res = node_res.get(actual_cmd_key, {})
                output = cmd_res.get("output", "").strip()
                return output if output else f"[WARN] {node_name} 命令 '{command}' 无输出。"
            else:
                return f"[ERROR] {node_name} 命令 '{command}' 在响应中未找到。"
        except Exception as e:
            return f"[ERROR] 执行命令失败: {e}".strip()

    def get_topo_json(self):
        """获取拓扑JSON（健壮版）"""
        topo = self.lab.remote_topo
        
        # 情况1：已经是字典（Dict），直接返回
        if isinstance(topo, dict):
            return topo
            
        # 情况2：是字符串（String），需要解析
        if isinstance(topo, str):
            try:
                # ！！！注意这里有个 's'，是 json.loads (Load String) ！！！
                return json.loads(topo)
            except Exception as e:
                print(f"[Fatal Error] 拓扑数据解析失败: {e}")
                print(f"原始数据片段: {topo[:100]}...") # 打印前100个字符用于调试
                return {"hosts": {}, "switches": {}, "routers": {}} # 返回空结构防止 KeyError

        # 情况3：其他未知类型
        print(f"[Warn] 未知的拓扑数据类型: {type(topo)}")
        return {"hosts": {}, "switches": {}, "routers": {}}

    def get_all_nodes(self) -> List[str]:
        """获取所有已部署的节点名，并排序保证输出顺序稳定"""
        
        return self.lab.get_all_nodes()

    def get_all_hosts(self) -> List[str]:
        """获取所有已部署的主机名"""
        
        return self.lab.get_all_hosts()
    
    def get_all_ovs(self) -> List[str]:
        
        return self.lab.get_all_ovs()
    
    def get_all_bmv2(self) -> List[str]:
        
        return self.lab.get_all_bmv2()

    def get_all_routers(self) -> List[str]:
        
        return self.lab.get_all_routers()

    def get_host_ip(self, host_name: str) -> Optional[str]:
        """
        获取主机 IPv4 地址（默认只有一个网卡）
        """
        topo = self.get_topo_json() 
        interfaces = topo["hosts"][host_name]["interfaces"]
        if interfaces and isinstance(interfaces, list):
            ip = interfaces[0].get("ip")
            return ip if ip else None
        return None
    
    def _get_host_interface_name(self, host_name: str) -> Optional[str]:
        """
        获取主机的唯一接口名称（假设每个主机只有一个接口）。
        """
        intfaces_string: str = self._run_cmd(host_name, "ls /sys/class/net") # 所有接口的字符串
        
        # 将字符串按空白符分割成列表，然后获取最后一个元素
        # 例如："eth0  lo  tor1_1" -> ["eth0", "lo", "tor1_1"] -> "tor1_1"
        interfaces = intfaces_string.strip().split()
        if interfaces:
            # 排除 "lo" (loopback) 接口，如果有其他接口的话
            # 如果只有一个接口且是lo，则返回lo。否则返回最后一个非lo接口
            non_lo_interfaces = [intf for intf in interfaces if intf != "lo"]
            if non_lo_interfaces:
                return non_lo_interfaces[-1] # 返回最后一个非lo接口
            elif "lo" in interfaces and len(interfaces) == 1:
                return "lo" # 如果只有lo接口，则返回lo
        return None # 如果没有找到任何接口
    
    def get_all_ryu_controllers(self) -> List[str]:
        """
        获取拓扑中所有的 Ryu 控制器节点名称
        """
        topo_data = self.get_topo_json()
        
        # 兼容完整的 JSON 结构 (包含 project -> topo) 以及直接的 topo 结构
        if "project" in topo_data and "topo" in topo_data["project"]:
            topo = topo_data["project"]["topo"]
        else:
            topo = topo_data

        controllers = []
        
        # 从 hosts 中筛选出 subtype 为 ryu/new_ryu 的节点
        for name, info in topo.get("hosts", {}).items():
            subtype = info.get("subtype", "")
            image_name = info.get("image_name", "")
            if subtype in ["ryu", "new_ryu"] or "ryu" in image_name:
                controllers.append(name)
                
        # 兼容独立的 controllers 字典（部分拓扑结构可能会放在这里）
        for name in topo.get("controllers", {}).keys():
            if name not in controllers:
                controllers.append(name)
                
        return controllers

    def ping_pair(self, host_name1: str, host_name2: str) -> str:
        """
        返回两个主机 ping 测试结果

        Args:
            host_name1: 发起 ping 的主机
            host_name2: 被 ping 的主机

        Return:
            ping 结果的字符串
        """
        ping_ip = self.get_host_ip(host_name2)
        if not ping_ip:
            return f"[ERROR] {host_name2} 无有效 IP，无法 ping\n" # 加上换行符保持格式一致
        
        cmd = f"ping {ping_ip} -c 5"
        # 直接使用已优化的 _run_cmd 函数来执行命令并获取输出
        output = self._run_cmd(host_name1, cmd, timeout=100) 
        return output + "\n"
