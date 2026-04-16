from dotenv import load_dotenv
load_dotenv() 
import time
from KlonetAPI import *
from base_netenv import NetworkEnvBase

class SDNStarTopo(NetworkEnvBase):
    """
    SDN OpenFlow 场景 (规模扩容): 1 Controller, 6 OVS, 12 Hosts (共 19 节点)
    """
    CTRL_IP = "192.168.100.1"
    CTRL_PORT = "6653"
    
    def __init__(self, lab_name="sdn_openflow"):
        super().__init__(lab_name=lab_name)

        # 1. 创建节点
        self.controller = self.lab.add_node("controller", self.lab.images["new_ryu"], x=400, y=100)
        self.s0 = self.lab.add_node("s0", self.lab.images["ovs"], x=400, y=300) # 核心 OVS
        
        edge_ovs = [self.lab.add_node(f"s{i}", self.lab.images["ovs"], x=150*i, y=500) for i in range(1, 6)]
        hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=70*i, y=700) for i in range(1, 13)]

        # 2. 创建链路
        self.lab.add_link(self.controller, self.s0, link_name="link_ctrl_s0")

        # 数据平面连通
        for s in edge_ovs: self.lab.add_link(self.s0, s)
        
        # 分配主机 (S1配2台, S2配3台, S3配2台, S4配3台, S5配2台)
        distribution = [2, 3, 2, 3, 2]
        host_idx = 0
        for i, count in enumerate(distribution):
            for _ in range(count):
                self.lab.add_link(edge_ovs[i], hosts[host_idx])
                host_idx += 1

        # 3. 部署
        self.deploy()
        time.sleep(15)

        # 4. SDN 配置
        self.config(senario="sdn")
        self._start_ryu_process()

    def _start_ryu_process(self):
        print("Starting Ryu Controller Process...")
        self.lab.execute("controller", "pkill -9 -f ryu-manager")
        log_file = "/tmp/ryu.log"
        ryu_cmd_inner = f"nohup python -m ryu.cmd.manager --verbose --ofp-tcp-listen-port {self.CTRL_PORT} --observe-links ryu.app.simple_switch_13 ryu.app.ofctl_rest > {log_file} 2>&1 &"
        self.lab.execute("controller", f"bash -c '{ryu_cmd_inner}'")
        
        for _ in range(15):
            time.sleep(1)
            output = self.lab.execute("controller", f"cat {log_file}")
            if isinstance(output, dict) and "controller" in output:
                txt = str(output["controller"])
                if "loading app" in txt or "BRICK" in txt:
                    print("✅ Ryu started successfully.")
                    return

def parse_klonet_output(node_name, response_dict):
    if not isinstance(response_dict, dict): return str(response_dict)
    node_data = response_dict.get(node_name)
    if not node_data: return ""
    for key, val in node_data.items():
        if isinstance(val, dict) and 'output' in val:
            return val['output'].strip()
    return str(node_data)

if __name__ == "__main__":
    Lab_SDN = SDNStarTopo()
    print("3. Checking OVS Controller Target (s5)...")
    res = Lab_SDN.lab.execute("s5", "ovs-vsctl show")
    print(parse_klonet_output("s5", res))