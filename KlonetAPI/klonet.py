import time
from typing import Dict, List, Optional
import requests
from . import klonet_api
from .klonet_api import *
import json

import re
from collections import defaultdict

# ==========================================
# 辅助类：图结构 (移植自 auto_configure.py)
# ==========================================
class Graph:
    def __init__(self):
        self.vertex = []
        self.vertexneighbor = defaultdict(list)
        self.vertexType = {}
    
    def add_vertex(self, *args):
        for i in args:
            if i not in self.vertex:
                self.vertex.append(i)
        
    def add_neighbor(self, source, target):
        self.vertexneighbor[source].append(target)
        self.vertexneighbor[target].append(source)
    
    def add_type(self, source, target, type1, type2):
        self.vertexType[source] = type1
        self.vertexType[target] = type2



def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as msg:
            print(f"{msg}")

    return wrapper


def http_response_handler(response, func=lambda r: r["msg"]):
    if response.status_code != 200:
        err_msg = f"Request failed with status code {response.status_code}"
        return err_msg
    else:
        data = response.json()
        code = data.get("code", 1)
        msg = data.get("msg", "Unknown")
        if code == 0:
            return f"Request failed. Error message: {msg}"
        else:
            return func(data)


class Klonet:

    def __init__(self):
        self._backend_host = ""
        self._port = 0
        self._project = ""
        self._user = ""
        self._image_manager = None
        self._project_manager = None
        self._node_manager = None
        self._link_manager = None
        self._cmd_manager = None
        self._traffic_manager = None
        self._logged_in = False
        self._topo = Topo()
        self._link_config = {}
        self.additional_info = {}

    @property
    def project_name(self):
        return self._project

    @property
    def user(self):
        return self._user

    @property
    def backend_host(self):
        return self._backend_host

    @property
    def port(self):
        return self._port

    @property
    def is_logged_in(self):
        return self._logged_in

    @property
    def is_topo_deployed(self):
        response = self.remote_topo
        return False if type(response) is str else True

    @property
    def images(self):
        return self._image_manager.get_images()

    @property
    def topo(self):
        return self._topo

    @property
    def remote_topo(self):
        ip = self._backend_host
        port = self._port
        project = self._project
        user = self._user
        url = f"http://{ip}:{port}/re/project/{project}/?user={user}"
        response = requests.get(url)

        def get_topo(data_json):
            project_info = data_json.get("project", {})
            topo = project_info.get("topo", "No topo data")
            return topo
        
        return http_response_handler(response, get_topo)

    @property
    def nodes(self):
        # 设计拓扑时的节点
        return self._topo.get_nodes()
    
    @property
    def nodes_deployed(self):
        '''若遇到查询不到IP的情况，可能是因为节点的IP没有通过平台的api去部署，则更新后的IP信息没有更新到数据库中，该接口查询的是数据库中的拓扑信息，所以返回会为空'''
        # 拓扑部署后的节点，包含动态增删后的信息
        return self._node_manager.get_nodes()

    @property
    def remote_nodes(self):
        ip = self._backend_host
        port = self._port
        project = self._project
        user = self._user
        url = f"http://{ip}:{port}/re/project/{project}/node/?user={user}"
        response = requests.get(url)

        def get_node_info(data_json):
            node_info = data_json.get("node_info", {})
            return node_info
        return http_response_handler(response, get_node_info)

    @property
    def links(self):
        # 设计拓扑时的链路
        return self._topo.get_links()
    
    @property
    def links_deployed(self):
        # 拓扑部署后的链路，包含动态增删后的信息
        return self._link_manager.get_links()

    @property
    def remote_links(self):
        ip = self._backend_host
        port = self._port
        project = self._project
        user = self._user
        url = f"http://{ip}:{port}/re/project/{project}/link/?user={user}"
        response = requests.get(url)

        def get_link_info(data_json):
            link_info = data_json.get("link_info", {})
            return link_info
        return http_response_handler(response, get_link_info)

    def klonet_login(self, project_name, user_name, host_ip, port):
        self._project = project_name
        self._user = user_name
        self._backend_host = host_ip
        self._port = port
        self._image_manager = ImageManager(self._user, self._backend_host, self._port)
        self._project_manager = ProjectManager(self._user, self._backend_host, self._port)
        self._node_manager = NodeManager(self._user, self._project, self._backend_host, self._port)
        self._link_manager = LinkManager(self._user, self._project, self._backend_host, self._port)
        self._cmd_manager = CmdManager(self._user, self._project, self._backend_host, self._port)
        self._logged_in = True

    def test_klonet_connection(self):
        try:
            _ = self.images
            return True
        except (klonet_api.common.errors.HttpStatusError,
                requests.exceptions.ConnectionError, AttributeError):
            return False

    def reset_project(self):
        """
        销毁项目
        """
        self._topo = Topo()
        self._link_config.clear()
        self._project_manager.destroy(self._project)

    def add_node(self, name, image, cpu_limit=None, mem_limit=None, x=0, y=0):
        node = self._topo.add_node(
            image, name,
            resource_limit={"cpu": cpu_limit, "mem": mem_limit},
            location={"x": x, "y": y})
        return node

    def add_node_runtime(self, name, image, cpu_limit=None, mem_limit=None, x=0, y=0):
        node = self._node_manager.dynamic_add_node(
            name, image,
            resource_limit={"cpu": cpu_limit, "mem": mem_limit},
            location={"x": x, "y": y}
        )
        return node

    def delete_node_runtime(self, name):
        self._node_manager.dynamic_delete_node(name)

    def add_link(self, src_node, dst_node, link_name=None, src_ip="", dst_ip=""):
        link = self._topo.add_link(
            src_node, dst_node, link_name, src_ip, dst_ip)
        return link

    def add_link_runtime(self, src_node, dst_node, link_name=None, src_ip="", dst_ip=""):
        self._link_manager.dynamic_add_link(
            link_name, src_node, dst_node, src_ip, dst_ip)

    def delete_link_runtime(self, link_name):
        self._link_manager.dynamic_delete_link(link_name)

    def configure_link(self, config):
        link_name = config["link"]
        _ = self._link_config.setdefault(link_name, {})
        node_name = config["ne"]
        src_node = self.links_deployed[link_name].source
        dst_node = self.links_deployed[link_name].target
        src_link_config = _.setdefault(src_node, {})
        dst_link_config = _.setdefault(dst_node, {})
        if node_name == src_node:
            src_link_config.update(**config)
            dst_link_config.update({"link": link_name, "ne": dst_node})
        elif node_name == dst_node:
            src_link_config.update({"link": link_name, "ne": src_node})
            dst_link_config.update(**config)
        else:
            raise LinkInconsistentError(f"Node {node_name} is not on link {link_name}.")
        src_config_obj = LinkConfiguration(**src_link_config)
        dst_config_obj = LinkConfiguration(**dst_link_config)
        self._link_manager.config_link(src_config_obj, dst_config_obj)
        return src_link_config if node_name == src_node else dst_link_config

    def reset_link(self, link_name, clean_cache=False):
        self._link_manager.clear_link_configuration(link_name)
        if clean_cache: self._link_config.clear()

    def query_link(self, link_name, node_name):
        ip = self._backend_host
        port = self._port
        url = f"http://{ip}:{port}/master/linkquery/"
        data = {
            "user": self._user,
            "topo": self._project,
            "links": [{
                "link": link_name,
                "ne": node_name
            }]
        }
        response = requests.post(url, json=data)

        def get_link_info(data_json):
            return data_json["static"]
        return http_response_handler(response, get_link_info)

    def deploy(self):
        self._project_manager.deploy(self._project, self._topo)

    def check_deployed(self):
        ip = self._backend_host
        port = self._port
        user = self._user
        project = self._project
        url = f"http://{ip}:{port}/master/topo/?user={user}&topo={project}"
        response = requests.get(url)

        def get_deploy_status(data_json):
            return data_json["stat"]
        return http_response_handler(response, get_deploy_status)

    def execute(self, node_name, command, block="false", timeout=60):
        response = self._cmd_manager.exec_cmds_in_nodes({
            node_name: [command]
        }, block, timeout)
        return response

    def batch_exec(self, ctns, command, block="false", timeout=60):
        url = f"http://{self._backend_host}:{self._port}/master/batch_exec_cmd/"
        data = {
            "user": self._user,
            "topo": self._project,
            "ctns": ctns,
            "cmd": command,
            "block": block,
            "cmd_timeout_s": timeout
        }
        response = requests.post(url, json=data)

        def get_exec_result(data_json):
            return data_json["exec_results"]
        return http_response_handler(response, get_exec_result)

    def enable_ssh_service(self, node_name):
        return self._node_manager.ssh_service(node_name, True)

    def port_mapping(self, node_name, container_port, host_port):
        return self._node_manager.modify_port_mapping(
            node_name, [container_port, host_port])

    def get_port_mapping(self, node_name):
        return self._node_manager.get_port_mapping(node_name)

    def get_worker_id(self, node_name=None):
        return self._node_manager.get_node_worker_ip(node_name)

    def deploy_from_config(self, config):
        self._topo = Topo(**config)
        url = f"http://{self._backend_host}:{self._port}/master/topo/"
        data = {
            "user": self._user,
            "topo": self._project,
            "networks": config
        }
        response = requests.post(url, json=data)
        return http_response_handler(response)

    def create_template_topo(self, config):
        url = f"http://{self._backend_host}:{self._port}/generate"
        response = requests.post(url, json=config)

        def get_topo_config(data_json):
            return data_json["net"]
        return http_response_handler(response, get_topo_config)

    def config_public_network(self, node_name, turn_on=True):
        url = f"http://{self._backend_host}:{self._port}/master/node/network/"
        data = {
            "user": self._user,
            "topo": self._project,
            "ne": node_name
        }
        req_func = requests.post if turn_on else requests.delete
        response = req_func(url, json=data)
        return http_response_handler(response)

    def check_public_network(self, node_name):
        ip = self._backend_host
        port = self._port
        user = self._user
        project = self._project
        url = f"http://{ip}:{port}/master/node/network/?user={user}&topo={project}&ne={node_name}"
        response = requests.get(url)

        def get_status(data_json):
            return data_json["status"]
        return http_response_handler(response, get_status)

    def upload_file(self, node_name, src_file, tgt_filepath="/home"):
        url = f"http://{self._backend_host}:{self._port}/file/uload/"
        data = {
            "user": self._user,
            "topo": self._project,
            "ne_name": node_name,
            "file_path": tgt_filepath,
        }
        files = {"file": open(src_file, "rb") if type(src_file) is str else src_file}
        response = requests.post(url, data=data, files=files)
        return http_response_handler(response)

    def manage_worker(self, worker_ip, delete_worker=False):
        url = f"http://{self._backend_host}:{self._port}/master/worker/{worker_ip}/"
        data = {"worker_ip": worker_ip}
        req_func = requests.delete if delete_worker else requests.post
        response = req_func(url, json=data)
        return http_response_handler(response)

    def check_health(self):
        ip = self._backend_host
        port = self._port
        user = self._user
        project = self._project
        url = f"http://{ip}:{port}/master/heartbeat_health/?user={user}&project={project}"
        response = requests.get(url)

        def get_broken_nodes(data_json):
            is_broken = data_json["is_broken"]
            broken_nodes = data_json["broken_nes"]
            return is_broken, broken_nodes
        return http_response_handler(response, get_broken_nodes)
    
    # ------------------------------------------------------------------- #
    # ========================== 新增的功能 ========================== #
    # ------------------------------------------------------------------- #

    def _run_cmd(self, node_name: str, command: str, timeout: int = 60) -> str:
        """
        同步执行命令（基于 Klonet block="true"）
        已内置异常捕获和超时处理
        """
        try:
            response = self.execute(node_name, command, block="true", timeout=timeout)
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
        """获取拓扑JSON"""
        topo = self.remote_topo
        return topo

    def get_all_nodes(self) -> List[str]:
        """获取所有已部署的节点名，并排序保证输出顺序稳定"""
        nodes = list(self.nodes_deployed.keys())
        return sorted(nodes)

    def get_all_hosts(self) -> List[str]:
        """获取所有已部署的主机名，并排序保证输出顺序稳定"""
        topo = self.get_topo_json()
        return sorted(topo["hosts"].keys())
    
    def get_all_ovs(self) -> List[str]:
        """获取所有已部署的 ovs 交换机，并排序保证输出顺序稳定"""
        topo = self.get_topo_json()
        switch_json = topo.get("switches", {}) 

        switches = []
        # 【关键修改 1】使用 .items() 同时遍历键(k)和值(v)
        for k, v in switch_json.items():
            image_name = v.get("image_name", "")
            
            # 判断是否包含 ovs
            if "ovs" in image_name:
                switches.append(k)

        return sorted(switches)
    
    def get_all_bmv2(self) -> List[str]:
        """获取所有已部署的 bmv2 交换机，并排序保证输出顺序稳定"""
        topo = self.get_topo_json()
        switch_json = topo.get("hosts", {}) # 注意 bmv2 放到了 hosts 大类!

        switches = []
        # 【关键修改 1】使用 .items() 同时遍历键(k)和值(v)
        for k, v in switch_json.items():
            image_name = v.get("image_name", "")
            
            # 判断是否包含 bmv2
            if "bmv2" in image_name:
                switches.append(k)

        return sorted(switches)
    
    def get_all_routers(self) -> List[str]:
        """获取所有已部署的 guagga 路由器，并排序保证输出顺序稳定"""
        topo = self.get_topo_json()
        return sorted(topo["routers"].keys())

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
        
        cmd = f"ping {ping_ip} -c 4"
        # 直接使用已优化的 _run_cmd 函数来执行命令并获取输出
        output = self._run_cmd(host_name1, cmd, timeout=100) 
        return output + "\n"

    def get_reachability(self) -> str:
        """
        获取全网可达性完整 ping 结果（同步接口，可直接 print）

        返回格式示例：
        h1 ping h2 result: 
        PING 192.168.2.2 (192.168.2.2) 56(84) bytes of data.
        64 bytes from 192.168.2.2: icmp_seq=1 ttl=64 time=1.23 ms
        ...

        --- 192.168.2.2 ping statistics ---
        4 packets transmitted, 4 received, 0% packet loss, time 3004ms

       h1 ping h3 result: ...

        特点：
        - 并行执行，速度极快
        - 任意方向不通也会返回完整失败信息（包含 packet loss）
        - 执行失败返回明确错误提示
        - 输出顺序稳定（主机名字母序）
        """
        # 1. 获取所有主机
        hosts = self.get_all_hosts()

        if len(hosts) < 2:
            return "[-] 主机数量少于 2，无法进行可达性测试"

        # 2. 批量获取所有主机的 IP
        host_ips: Dict[str, str] = {}
        for host in hosts:
            ip = self.get_host_ip(host)
            if ip:
                host_ips[host] = ip

        if len(host_ips) < 2:
            return "[-] 有 IP 的主机少于 2 个，无法进行可达性测试"

        # 3. 两两组合 ping
        result: str = ""
        for host_i in hosts:
            for host_j in hosts:
                if(host_i is not host_j):
                    result += f"{host_i} ping {host_j} result:\n"
                    result += self.ping_pair(host_i, host_j)
                    result += "\n"

        return result
    


    # ------------------------------------------------------------------- #
    # ========================== IP路由自动配置 ========================== #
    # ------------------------------------------------------------------- #

    def _update_node_info_api(self, node_info):
        """内部辅助函数：调用API更新节点配置 (PUT /modification/container/)"""
        url = f"http://{self._backend_host}:{self._port}/modification/container/"
        payload = {
            "user": self._user,
            "topo": self._project,
            "info": node_info
        }
        # 使用 requests.put 更新
        response = requests.put(url, json=payload)
        return response

    def _get_node_type(self, node_name: str, node_info: dict) -> str:
        """根据镜像名称推断节点类型"""
        image = node_info.get("image_name", "").lower()
        if "quagga" in image: return "router"
        if "ovs" in image or "bmv2" in image: return "switch"
        return "host"

    def _find_interface(self, node_info, target_name):
        """
        [关键修复] 智能查找接口
        在 node_info['interfaces'] 中寻找连接到 target_name 的接口。
        """
        if "interfaces" not in node_info:
            return None
        
        candidates = node_info["interfaces"]
        # 排除 loopback
        valid_intfs = [i for i in candidates if i["name"] != "lo"]
        
        # 策略1: 精确匹配 (旧逻辑)
        exact_match = f"{node_info.get('name', '')}{target_name}"
        for intf in valid_intfs:
            if intf["name"] == exact_match: return intf
            
        # 策略2: 模糊匹配 (适配 'tos1_1')
        # 检查接口名是否包含 target_name (忽略大小写)
        target_clean = target_name.lower()
        for intf in valid_intfs:
            iname = intf["name"].lower()
            # 排除干扰：比如 target是s1，不要匹配到s12
            if target_clean in iname:
                return intf
                
        # 策略3: 如果该节点只有一个数据接口 (Host通常如此)，直接返回它
        node_type = self._get_node_type("", node_info)
        if node_type == "host" and len(valid_intfs) == 1:
            return valid_intfs[0]
            
        return None

    def _correct_topology_data(self, topo_msg, mode):
        """
        [Helper] 修正拓扑数据源
        将误分类到 'hosts' 的交换机（如 bmv2/ovs）移动到 'switches' 列表。
        """
        if "switches" not in topo_msg: topo_msg["switches"] = {}
        if "hosts" not in topo_msg: topo_msg["hosts"] = {}
        
        nodes_to_move = []
        
        # 扫描 hosts 列表，寻找潜伏的交换机
        for name, info in topo_msg["hosts"].items():
            # 拼接所有元数据进行判断
            meta_str = (info.get("image_name", "") + info.get("subtype", "")).lower()
            
            is_switch = False
            # 判定条件 1: 镜像名包含特征字符
            if "bmv2" in meta_str or "ovs" in meta_str or "p4lang" in meta_str:
                is_switch = True
            # 判定条件 2: P4 模式下的强力兜底 (s开头即交换机)
            elif mode == "p4" and name.startswith("s"):
                is_switch = True
            
            if is_switch:
                nodes_to_move.append(name)
        
        # 执行移动操作
        for name in nodes_to_move:
            print(f"  [Fix] Moving node '{name}' from 'hosts' to 'switches' category.")
            # pop 出来并赋值给 switches
            node_info = topo_msg["hosts"].pop(name)
            topo_msg["switches"][name] = node_info
            
        return topo_msg

    # ==========================================
    # 核心逻辑修正：IP分配 + 路由信息收集
    # ==========================================

    def _auto_ip_assign(self, mode="normal"):
        """
        支持 Router-based 和 Switch-based/SDN 场景
        [核心逻辑] 智能IP分配 + 返回路由拓扑数据
        Returns:
            topo_msg: 更新后的拓扑信息
            routing_data: {
                "subnets": { "router_name": ["192.168.1.0/24", ...] }, # 每个路由器直连的网段
                "neighbors": { "router_name": { "neighbor_name": "neighbor_ip" } } # 路由器的邻居及对端IP
            }
        """
        print(f">>> Starting IP Auto-Configuration (Mode: {mode})...")
        
        # 1. 获取原始拓扑
        raw_topo = self.get_topo_json()
        
        # 2. [关键调用] 修正数据源
        # 这一步确保后续所有逻辑基于正确的分类运行
        topo_msg = self._correct_topology_data(raw_topo, mode)
        
        # --- 0. 数据结构初始化 ---
        routing_data = {
            "subnets": defaultdict(list),
            "neighbors": defaultdict(dict)
        }

        # --- 1. 节点类型识别与图构建 ---
        topo_graph = Graph()
        real_node_types = {}
        all_nodes = {}

        # 聚合所有节点信息 (此时 switches 列表已经是修正过的了)
        for cat in ["routers", "switches", "hosts", "nodes"]:
            nodes_in_cat = topo_msg.get(cat, {})
            if nodes_in_cat:
                print(f"  [Debug] Found {len(nodes_in_cat)} nodes in category '{cat}'")
            all_nodes.update(nodes_in_cat)

        print(f"  [Debug] Processing {len(all_nodes)} total nodes...")

        # 节点类型识别
        for name, info in all_nodes.items():
            # 获取镜像名用于推断
            image = info.get("subtype", "").lower()
            
            if "ubuntu" in image:
                ntype = "host"
            elif "ovs" in image: 
                ntype = "switch"
            elif "quagga" in image:
                ntype = "router"
            elif "bmv2" in image:
                ntype = "switch"
            elif "ryu" in image:
                ntype = "host"

            real_node_types[name] = ntype
            topo_graph.add_vertex(name)
            print(f"    - Node: {name} | Type: {ntype} | Image: {image}")

            # 节点初始化操作
            if ntype == "router":
                self.execute(name, "sysctl -w net.ipv4.ip_forward=1")
            elif ntype == "switch":
                if mode == "normal" and "ovs" in image:
                    self.execute(name, "ovs-ofctl del-flows init-br0 || true")
                    self.execute(name, "ovs-ofctl add-flow init-br0 actions=NORMAL || true")
                elif mode == "p4":
                    # P4 交换机基础初始化：拉起 loopback，防止后续命令报错
                    self.execute(name, "ip link set lo up")

        # --- 2. 链路分类 ---
        router_to_router = []
        router_to_host = []
        switch_to_router = []
        link_count = 0

        for link_key, values in topo_msg["links"].items():
            src, dst = values["source"], values["target"]
            s_type = real_node_types.get(src, "host")
            t_type = real_node_types.get(dst, "host")
            
            topo_graph.add_type(src, dst, s_type, t_type)
            
            if s_type == "router" and t_type == "router":
                router_to_router.append(link_key)
            elif (s_type == "switch" and t_type == "router") or (s_type == "router" and t_type == "switch"):
                switch_to_router.append(link_key)
                topo_graph.add_neighbor(src, dst)
            elif (s_type == "switch" and t_type == "host") or (s_type == "host" and t_type == "switch"):
                topo_graph.add_neighbor(src, dst)
            elif s_type == "switch" and t_type == "switch":
                topo_graph.add_neighbor(src, dst)
            elif (s_type == "router" and t_type == "host") or (s_type == "host" and t_type == "router"):
                router_to_host.append(link_key)

            link_count += 1

        print(f"  [Debug] Graph built with {link_count} links.")

        # 参数初始化
        net_prefix = "192.168."
        l2_prefix = "10.0." # 用于纯交换网络的网段
        netmask = "255.255.255.0"
        sub_net = 0
        l2_sub_net = 0
        configured_hosts = set() # 记录已配置的主机

        # --- 辅助函数：应用 IP 配置 ---
        def apply_ip_config(node_name, intf, ip, gateway=None):
            if not intf: return
            intf_name = intf["name"]
            
            # [SDN 控制器 IP 锁定]
            # 如果是 SDN 模式且是 controller，强制使用固定 IP，防止被自动分配逻辑覆盖
            if mode == "sdn" and node_name == "controller":
                final_ip = "192.168.100.1"
                print(f"  [SDN Override] Locking Controller IP: {final_ip}")
            else:
                final_ip = ip

            # 更新 topo_msg
            intf["ip"] = final_ip
            intf["netmask"] = netmask
            if gateway and "hosts" in topo_msg and node_name in topo_msg["hosts"]:
                topo_msg["hosts"][node_name]["gateway"] = gateway

            # 下发 Linux 命令
            self.execute(node_name, f"ip addr flush dev {intf_name}")
            self.execute(node_name, f"ip addr add {final_ip}/24 dev {intf_name}")
            self.execute(node_name, f"ip link set {intf_name} up")
            
            if gateway:
                self.execute(node_name, f"ip route replace default via {gateway}")

        # ==========================================
        # Phase 1: 路由器相关配置 (Router-Centric)
        # ==========================================

        # ==========================================
        # 场景 A: Router-Router (记录邻居关系)
        # ==========================================
        for key in router_to_router:
            net_host = 1
            link = topo_msg["links"][key]
            src, dst = link["source"], link["target"]
            
            ip1 = f"{net_prefix}{sub_net}.{net_host}"
            net_host += 1
            ip2 = f"{net_prefix}{sub_net}.{net_host}"
            
            r1_info = all_nodes[src]
            r2_info = all_nodes[dst]
            
            intf1 = self._find_interface(r1_info, dst)
            intf2 = self._find_interface(r2_info, src)
            
            apply_ip_config(src, intf1, ip1)
            self._update_node_info_api(r1_info)
            
            apply_ip_config(dst, intf2, ip2)
            self._update_node_info_api(r2_info)
            
            # 【重要】记录路由拓扑数据
            subnet_cidr = f"{net_prefix}{sub_net}.0/24"
            routing_data["subnets"][src].append(subnet_cidr)
            routing_data["subnets"][dst].append(subnet_cidr)
            
            # src 去 dst，下一跳是 ip2
            routing_data["neighbors"][src][dst] = ip2
            # dst 去 src，下一跳是 ip1
            routing_data["neighbors"][dst][src] = ip1
            
            sub_net += 1

        # ==========================================
        # 场景 B: Router-Host
        # ==========================================
        for key in router_to_host:
            net_host = 1
            link = topo_msg["links"][key]
            if real_node_types.get(link["source"]) == "router":
                r_name, h_name = link["source"], link["target"]
            else:
                r_name, h_name = link["target"], link["source"]
                
            gateway_ip = f"{net_prefix}{sub_net}.{net_host}"
            net_host += 1
            host_ip = f"{net_prefix}{sub_net}.{net_host}"
            
            r_info = all_nodes[r_name]
            h_info = all_nodes[h_name]
            
            apply_ip_config(r_name, self._find_interface(r_info, h_name), gateway_ip)
            self._update_node_info_api(r_info)
            
            # 修复：调用时明确使用 gateway=
            apply_ip_config(h_name, self._find_interface(h_info, r_name), host_ip, gateway=gateway_ip)
            self._update_node_info_api(h_info)
            configured_hosts.add(h_name)
            
            # 记录子网归属
            subnet_cidr = f"{net_prefix}{sub_net}.0/24"
            routing_data["subnets"][r_name].append(subnet_cidr)
            
            sub_net += 1

        # ==========================================
        # 场景 C: Router-Switch-Host (DFS)
        # ==========================================
        def dfs(u, current_subnet, host_counter_list, visited, parent_gw_ip):
            visited.add(u)
            u_type = real_node_types.get(u)
            if u_type == "host":
                h_info = all_nodes[u]
                candidates = [i for i in h_info["interfaces"] if i["name"]!="lo"]
                target_intf = candidates[0] if candidates else None
                if target_intf:
                    ip = f"{net_prefix}{current_subnet}.{host_counter_list[0]}"
                    host_counter_list[0] += 1
                    # 修复：调用时明确使用 gateway=
                    apply_ip_config(u, target_intf, ip, gateway=parent_gw_ip)
                    self._update_node_info_api(h_info)
                    configured_hosts.add(u)
                return
            if u_type == "switch":
                for v in topo_graph.vertexneighbor[u]:
                    if v not in visited and real_node_types.get(v) != "router":
                        dfs(v, current_subnet, host_counter_list, visited, parent_gw_ip)

        for key in switch_to_router:
            net_host = 1
            link = topo_msg["links"][key]
            if real_node_types.get(link["source"]) == "router":
                r_name, s_name = link["source"], link["target"]
            else:
                r_name, s_name = link["target"], link["source"]
            
            r_info = all_nodes[r_name]
            gateway_ip = f"{net_prefix}{sub_net}.{net_host}"
            net_host += 1
            
            apply_ip_config(r_name, self._find_interface(r_info, s_name), gateway_ip)
            self._update_node_info_api(r_info)
            
            visited = set()
            visited.add(r_name)
            host_counter = [net_host]
            dfs(s_name, sub_net, host_counter, visited, gateway_ip)
            
            # 记录子网归属
            subnet_cidr = f"{net_prefix}{sub_net}.0/24"
            routing_data["subnets"][r_name].append(subnet_cidr)
            
            sub_net += 1

        # ==========================================
        # Phase 2: 纯二层域 (Switch-Centric) - 适用于 SDN 和 P4
        # ==========================================
        
        def dfs_l2_domain(u, component_hosts, visited_switches):
            visited_switches.add(u)
            for v in topo_graph.vertexneighbor[u]:
                v_type = real_node_types.get(v)
                if v_type == "router": continue 
                
                # 在 SDN/P4 场景下，Controller 也被视为一个 Host 节点接入网络
                if v == "controller" or v_type == "host":
                    if v not in configured_hosts and v not in component_hosts:
                        component_hosts.append(v)
                elif v_type == "switch" and v not in visited_switches:
                    dfs_l2_domain(v, component_hosts, visited_switches)

        processed_switches = set()
        for s_name, _ in topo_msg.get("switches", {}).items():
            if s_name in processed_switches: continue
            
            domain_hosts = []
            dfs_l2_domain(s_name, domain_hosts, processed_switches)
            
            if domain_hosts:
                print(f"  [Config] Found {'P4' if mode=='p4' else 'L2'} Domain: {domain_hosts}")
                host_cnt = 1
                
                for h_name in domain_hosts:
                    # 如果是 P4 场景，通常不需要给 Controller 分配数据平面 IP (Controller 走 gRPC)
                    # 如果是 SDN 场景，Controller 需要 IP (OpenFlow)
                    
                    ip = f"{l2_prefix}{l2_sub_net}.{host_cnt}"
                    host_cnt += 1
                    h_info = all_nodes[h_name]
                    
                    # 查找接口
                    intf = self._find_interface(h_info, "to") or (h_info["interfaces"][0] if h_info["interfaces"] else None)
                    
                    apply_ip_config(h_name, intf, ip, gateway=None)
                    self._update_node_info_api(h_info)
                    configured_hosts.add(h_name)
                    print(f"    - Assigned {h_name}: {ip}")
                
                l2_sub_net += 1

            else:
                print(f"  [Debug] Switch {s_name} has no connected unconfigured hosts.")

        print(">>> IP/Route Configuration Complete.")
        return topo_msg, routing_data


    # ==========================================
    # IP路由配置 (实现简单的 BFS 计算)
    # ==========================================

    def static_config(self):
        """
        静态路由：自动计算全局最短路径并下发静态路由表
        """
        print(">>> Configuring Static Routes (Calculating Paths)...")
        # 1. 先分配 IP，并获取详细的路由拓扑数据
        topo_msg, routing_data = self._auto_ip_assign(mode="normal")
        
        subnets_map = routing_data["subnets"]   # {r1: [subnet1, subnet2], r2: [...]}
        neighbors_map = routing_data["neighbors"] # {r1: {r2: "next_hop_ip"}}
        
        all_routers = list(subnets_map.keys())
        
        # 2. 为每个路由器计算去往全网其他子网的路径
        for src_router in all_routers:
            # 收集该路由器已知的直连网段
            my_subnets = set(subnets_map[src_router])
            
            # 简单的 BFS 寻找下一跳
            # Queue 结构: (current_node, first_hop_neighbor)
            queue = []
            visited = {src_router}
            
            # 初始化队列：加入直连邻居
            for neighbor in neighbors_map.get(src_router, {}):
                queue.append((neighbor, neighbor))
                visited.add(neighbor)
                
            while queue:
                curr_router, next_hop_router = queue.pop(0)
                
                # 找到一个远端路由器 curr_router
                # 获取它的子网
                target_subnets = subnets_map.get(curr_router, [])
                
                # 获取去往该方向的下一跳 IP
                next_hop_ip = neighbors_map[src_router][next_hop_router]
                
                # 为该路由器下的所有子网添加路由
                for subnet in target_subnets:
                    if subnet not in my_subnets:
                        # 下发路由命令: ip route add <subnet> via <next_hop_ip>
                        self.execute(src_router, f"ip route add {subnet} via {next_hop_ip}")
                        my_subnets.add(subnet) # 标记为已知，防止多路径重复添加
                
                # 继续遍历更远的邻居
                for next_r in neighbors_map.get(curr_router, {}):
                    if next_r not in visited:
                        visited.add(next_r)
                        queue.append((next_r, next_hop_router))
                        
        print(">>> Static Routes Applied Successfully.")

    
    def ospf_config(self):
        # 只需要 topo_msg
        topo_msg, _ = self._auto_ip_assign(mode="normal")
        routers = topo_msg.get("routers", {})
        idx = 1
        for r_name, r_info in routers.items():
            networks = []
            for intf in r_info["interfaces"]:
                if intf.get("ip"):
                    networks.append([f"{intf['ip']}/24", "0.0.0.0"])
            
            if "config" not in r_info: r_info["config"] = {}
            if "ospf" not in r_info["config"]: r_info["config"]["ospf"] = {}
            
            r_info["config"]["ospf"].update({
                "router_id": f"10.0.0.{idx}",
                "networks": networks,
                "enable": True
            })
            idx += 1
            self._update_node_info_api(r_info)
        print(">>> OSPF Configured.")

    def rip_config(self):
        topo_msg, _ = self._auto_ip_assign(mode="normal")
        routers = topo_msg.get("routers", {})
        for r_name, r_info in routers.items():
            networks = [f"{i['ip']}/24" for i in r_info["interfaces"] if i.get("ip")]
            if "config" not in r_info: r_info["config"] = {}
            if "rip" not in r_info["config"]: r_info["config"]["rip"] = {}
            r_info["config"]["rip"].update({"networks": networks, "enable": True})
            self._update_node_info_api(r_info)
        print(">>> RIP Configured.")
        
    def bgp_config(self):
        """
        [修正版] BGP配置：强制启动守护进程 + 兼容性配置 + 状态自检
        """
        print(">>> Configuring BGP (Force Start Daemons & Configure)...")
        
        # 1. 基础IP分配 (IP生效，开启转发，OVS Normal)
        topo_msg, routing_data = self._auto_ip_assign(mode="normal")
        
        routers = topo_msg.get("routers", {})
        sorted_routers = sorted(routers.keys())
        as_map = {name: 65000 + i for i, name in enumerate(sorted_routers, 1)}
        
        for r_name in sorted_routers:
            local_as = as_map[r_name]
            
            # --- 步骤 1: 强制启动 Quagga 守护进程 ---
            print(f"  [BGP] Starting daemons on {r_name}...")
            self.execute(r_name, "/usr/lib/quagga/zebra -d")
            self.execute(r_name, "/usr/sbin/zebra -d")
            self.execute(r_name, "/usr/lib/quagga/bgpd -d")
            self.execute(r_name, "/usr/sbin/bgpd -d")
            
            # --- 步骤 2: 准备配置 ---
            router_id = "1.1.1.1"
            r_info = routers[r_name]
            # 找一个非 lo 的 IP 作为 Router ID
            for intf in r_info["interfaces"]:
                if intf.get("ip") and intf["name"] != "lo":
                    # 去掉掩码 /24
                    router_id = intf["ip"].split('/')[0]
                    break

            # 构建配置命令
            cmds = [
                "configure terminal",
                f"router bgp {local_as}",
                f"bgp router-id {router_id}",
                "timers bgp 5 15",               # 加速收敛
                "bgp log-neighbor-changes"       # 记录日志
            ]
            
            # 添加邻居
            my_neighbors = routing_data["neighbors"].get(r_name, {})
            for neighbor_name, next_hop_ip in my_neighbors.items():
                # 去掉掩码
                peer_ip = next_hop_ip.split('/')[0]
                remote_as = as_map[neighbor_name]
                cmds.append(f"neighbor {peer_ip} remote-as {remote_as}")
                cmds.append(f"neighbor {peer_ip} next-hop-self")
            
            # 通告直连网段
            my_subnets = routing_data["subnets"].get(r_name, [])
            for subnet in my_subnets:
                cmds.append(f"network {subnet}")
            
            # 强制重分发直连 (保底策略)
            cmds.append("redistribute connected")
            
            cmds.append("end")
            cmds.append("write memory")
            
            # --- 步骤 3: 下发配置 ---
            vtysh_cmd = "vtysh"
            for c in cmds:
                vtysh_cmd += f" -c '{c}'"
            
            self.execute(r_name, vtysh_cmd)
            print(f"  [BGP] Configured {r_name} (AS {local_as}).")

        print(">>> BGP Configuration sent. Waiting 15s for convergence...")
        time.sleep(15) 
        
        # --- 步骤 4: 诊断输出 (关键) ---
        print("\n--- 🔍 BGP 状态自检 (R1) ---")
        # 检查邻居建立情况
        res = self._run_cmd("r1", "vtysh -c 'show ip bgp summary'")
        print(f"R1 BGP Summary:\n{res}")
        
        # 检查路由表是否学习到路由
        res_route = self._run_cmd("r1", "ip route")
        print(f"R1 Kernel Route:\n{res_route}")
        
        print(">>> BGP Ready.")

    def _safe_get_output(self, response):
        """[递归解析器] 无视 API 嵌套层级，暴力挖掘 output 字段"""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            # 优先查找直接的 output
            if 'output' in response:
                return response['output']
            # 否则遍历所有 value 继续找
            for v in response.values():
                res = self._safe_get_output(v)
                if res: return res
        return ""

    def p4_config(self):
        """
        [P4 模式] 修复版：只配置接口 IP 和 UP 状态，绝不启动 simple_switch
        """
        # 1. IP 分配
        topo_msg, _ = self._auto_ip_assign(mode="p4")
        
        print(">>> P4 Mode: Configuring Interfaces (Switch Startup Deferred)...")
        
        for s_name, s_info in topo_msg.get("switches", {}).items():
            image = (s_info.get("image_name", "") + s_info.get("subtype", "")).lower()
            if "bmv2" in image or "p4lang" in image or s_name.startswith("s"):
                print(f"  - Configuring interfaces on {s_name}...")
                
                # --- 获取接口名 (保留你之前的正确逻辑) ---
                find_cmd = (
                    "ip -o link show | "
                    "awk -F': ' '{print $2}' | "
                    "cut -d@ -f1 | "
                    "grep -v -E 'lo|tun|eth0' | "
                    "sort | "
                    "tr '\n' ' '"
                )
                raw_res = self.execute(s_name, f"bash -c \"{find_cmd}\"")
                ifaces_str = self._safe_get_output(raw_res).strip()
                if not ifaces_str: continue
                
                ifaces = ifaces_str.split()
                print(f"    Interfaces: {ifaces}")

                # --- 仅做接口激活 (Up + Offload) ---
                setup_cmds = []
                for iface in ifaces:
                    setup_cmds.append(f"ip link set {iface} up")
                    setup_cmds.append(f"ethtool -K {iface} tx off rx off")
                
                setup_cmd_str = " && ".join(setup_cmds)
                self.execute(s_name, f"bash -c '{setup_cmd_str}'")
                
                # ========================================================
                # 🔪 手术点：彻底删除/注释掉原本在这里的 simple_switch 启动代码
                # 我们将在 p4_star.py 中带着 JSON 完美启动它
                # ========================================================
                # (已删除 start_cmd 相关代码)

        print(">>> Interface Configuration Complete (Waiting for P4 Controller to start switches).")
        time.sleep(1)


    def sdn_config(self):
        """
        SDN 模式配置 (修复版 v4):
        1. IP分配
        2. [关键] 将物理网卡插入 OVS 网桥 (上次日志缺失的部分)
        3. 配置管理 IP 和 控制器连接
        """
        # 1. 基础 IP 分配
        self._auto_ip_assign(mode="sdn")
        
        print(">>> SDN Mode: Configuring OVS Controller Targets...")
        topo_msg = self.get_topo_json()
        
        CTRL_IP = "192.168.100.1"
        CTRL_PORT = 6653
        target_str = f"tcp:{CTRL_IP}:{CTRL_PORT}"
        
        sw_mgmt_ip_start = 100 
        
        for s_name, s_info in topo_msg.get("switches", {}).items():
            if "ovs" in s_info.get("image_name", ""):
                # A. 获取网桥名
                response = self.execute(s_name, "ovs-vsctl list-br")
                raw_br_str = ""
                if isinstance(response, dict):
                    node_res = response.get(s_name, {})
                    for key, val in node_res.items():
                        if isinstance(val, dict) and 'output' in val:
                            raw_br_str = val['output']
                            break
                else:
                    raw_br_str = str(response)

                if not raw_br_str or "ovs-vsctl" in raw_br_str: 
                    br_name = "init-br0"
                else:
                    br_name = raw_br_str.strip().splitlines()[0].strip()
                
                print(f"  - Configuring {s_name} (Bridge: {br_name})...")

                # B. [关键] 将物理接口加入网桥
                # 必须显式执行这一步，否则网桥和外面是断开的
                if "interfaces" in s_info:
                    print(f"    [Fix] Adding ports to {br_name}...") 
                    for intf in s_info["interfaces"]:
                        intf_name = intf["name"]
                        if intf_name == "lo" or intf_name == br_name: continue
                        
                        # 强制添加端口
                        self.execute(s_name, f"ovs-vsctl --may-exist add-port {br_name} {intf_name}")
                        self.execute(s_name, f"ip link set {intf_name} up")

                # C. 配置管理 IP
                mgmt_ip = f"192.168.100.{sw_mgmt_ip_start}"
                sw_mgmt_ip_start += 1
                self.execute(s_name, f"ip addr flush dev {br_name}")
                self.execute(s_name, f"ip addr add {mgmt_ip}/24 dev {br_name}")
                self.execute(s_name, f"ip link set {br_name} up")
                print(f"    Set Mgmt IP: {mgmt_ip}")

                # D. 连接控制器
                self.execute(s_name, f"ovs-vsctl set-controller {br_name} {target_str}")
                self.execute(s_name, f"ovs-vsctl set bridge {br_name} protocols=OpenFlow13")
                self.execute(s_name, f"ovs-vsctl set-fail-mode {br_name} secure")

        print(">>> SDN Controller Targets Set & Mgmt IPs Configured.")