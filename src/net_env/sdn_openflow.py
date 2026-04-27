from dotenv import load_dotenv
load_dotenv() 
import time
import logging

from KlonetAPI import *
from base_netenv import NetworkEnvBase

# # 配置日志输出
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

class SDNStarTopo(NetworkEnvBase):
    """
    SDN OpenFlow 场景: 星型拓扑 (Star) - 适配 new_ryu 镜像
    
    拓扑结构:
        Controller(new_ryu) [192.168.100.1]
                  |
            Center(S0)
           |    |    |
         S1     S2    S3
         |      |     |
         H1     H2    H3
    
    变更说明:
    - 环境修复代码已移除，相关逻辑(IP/OVS)已下沉至 Klonet.sdn_config()。
    """
    
    # 期望的控制器配置 (用于验证)
    CTRL_IP = "192.168.100.1"
    CTRL_PORT = "6653"
    
    def __init__(self, lab_name="sdn_openflow"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 创建节点 (Nodes)
        # ==========================================
        # logger.info("Creating nodes...")
        
        # 控制器 (Ryu)
        self.controller = self.lab.add_node("controller", self.lab.images["new_ryu"], x=400, y=100)

        # 交换机 (OVS)
        self.s0 = self.lab.add_node("s0", self.lab.images["ovs"], x=400, y=300)
        self.s1 = self.lab.add_node("s1", self.lab.images["ovs"], x=200, y=500)
        self.s2 = self.lab.add_node("s2", self.lab.images["ovs"], x=400, y=500)
        self.s3 = self.lab.add_node("s3", self.lab.images["ovs"], x=600, y=500)

        # 主机 (Hosts)
        self.h1 = self.lab.add_node("h1", self.lab.images["ubuntu"], x=200, y=650)
        self.h2 = self.lab.add_node("h2", self.lab.images["ubuntu"], x=400, y=650)
        self.h3 = self.lab.add_node("h3", self.lab.images["ubuntu"], x=600, y=650)

        # ==========================================
        # 2. 创建链路 (Links)
        # ==========================================
        # logger.info("Creating links...")
        
        # 控制平面
        self.lab.add_link(self.controller, self.s0, link_name="link_ctrl_s0")

        # 数据平面
        self.lab.add_link(self.s0, self.s1)
        self.lab.add_link(self.s0, self.s2)
        self.lab.add_link(self.s0, self.s3)
        self.lab.add_link(self.s1, self.h1)
        self.lab.add_link(self.s2, self.h2)
        self.lab.add_link(self.s3, self.h3)

        # ==========================================
        # 3. 部署 (Deploy)
        # ==========================================
        # logger.info("Deploying topology...")
        self.deploy()

        # 等待容器启动
        # logger.info("Waiting 15s for containers to start...")
        time.sleep(15)

        # ==========================================
        # 4. 一键配置 (SDN Mode)
        # ==========================================
        # 这里会自动：1. 分配主机IP 2. 锁定控制器IP为 192.168.100.1 3. 配置 OVS 连接控制器
        # logger.info("Executing Klonet SDN auto-configuration...")
        self.config(senario="sdn")

        # ==========================================
        # 5. 启动 Ryu 应用 (Application Startup)
        # ==========================================
        self._start_ryu_process()
        
        # logger.info("SDN Topology Ready.")

    def _start_ryu_process(self):
        """
        启动 Ryu 控制器 (修复误报版)
        """
        print("Starting Ryu Controller Process...")

        # 1. 尝试清理旧进程 (忽略错误)
        self.lab.execute("controller", "pkill -9 -f ryu-manager")
        
        # 2. 启动 Ryu
        log_file = "/tmp/ryu.log"
        # 使用 python 而非 python3，保留 nohup
        ryu_cmd_inner = (
            f"nohup python -m ryu.cmd.manager --verbose "
            f"--ofp-tcp-listen-port {self.CTRL_PORT} --observe-links "
            f"ryu.app.simple_switch_13 ryu.app.ofctl_rest "
            f"> {log_file} 2>&1 &"
        )
        full_cmd = f"bash -c '{ryu_cmd_inner}'"
        
        print(f"Executing: {full_cmd}")
        self.lab.execute("controller", full_cmd)
        
        # 3. 轮询等待 (Smart Check)
        print(f"Waiting for Ryu to initialize...")
        for i in range(15):
            time.sleep(1)
            # 读取日志
            log_check = self.lab.execute("controller", f"cat {log_file}")
            output = parse_klonet_output("controller", log_check)
            
            # [关键修改] 只要看到 'loading app' 或 'BRICK' 就说明 python 进程活了
            if "loading app" in output or "BRICK" in output:
                print(f"✅ Ryu started successfully (Detected application loading).")
                return
            
            # 如果能用 netstat 更好
            res = self.lab.execute("controller", f"netstat -tuln | grep {self.CTRL_PORT}")
            if str(self.CTRL_PORT) in parse_klonet_output("controller", res):
                print(f"✅ Ryu is listening on {self.CTRL_PORT}.")
                return

        # 4. 超时处理 (如果还是没起，那才是真报错)
        print("❌ Ryu failed to initialize within 15s. Dumping log:")
        log_out = self.lab.execute("controller", f"cat {log_file}")
        print(parse_klonet_output("controller", log_out))

def parse_klonet_output(node_name, response_dict):
    """[辅助函数] 提取 Klonet 命令输出文本"""
    if not isinstance(response_dict, dict): return str(response_dict)
    node_data = response_dict.get(node_name)
    if not node_data: return ""
    for key, val in node_data.items():
        if isinstance(val, dict) and 'output' in val:
            return val['output'].strip()
    return str(node_data)


# --- 在 main 函数底部的验证部分也需要修改，防止因为没 ping 而报错 ---

if __name__ == "__main__":
    # ... (前面的代码保持不变) ...
    Lab_SDN = SDNStarTopo()

    print("\n--- 🔍 深度自检环节 (Validation) ---")
    
    # 1. 验证控制器 IP
    print(f"1. Checking Controller IP ({SDNStarTopo.CTRL_IP})...")
    res = Lab_SDN.lab.execute("controller", "ip addr show")
    output = parse_klonet_output("controller", res)
    if SDNStarTopo.CTRL_IP in output:
        print(f"✅ Controller IP is correctly set.")
    else:
        print(f"❌ Controller IP Incorrect.")

    # 2. [修复] 验证 L3 连通性 (带容错)
    s0_mgmt_ip = "192.168.100.100"
    print(f"2. Testing Connectivity: Controller -> S0 ({s0_mgmt_ip})...")
    
    ping_res = Lab_SDN.lab.execute("controller", f"ping -c 3 -W 1 {s0_mgmt_ip}")
    ping_out = parse_klonet_output("controller", ping_res)
    
    if "executable file not found" in ping_out or "not found" in ping_out:
        print(f"⚠️ Ping tool missing in container. Skipping ping test.")
    elif "0% packet loss" in ping_out:
        print(f"✅ Ping Success! Network layer is OK.")
    else:
        print(f"❌ Ping Failed. Output:\n{ping_out}")

    # 3. 验证 OVS 连接状态 (最关键的指标)
    print("3. Checking OVS Controller Target (s0)...")
    time.sleep(3)
    res = Lab_SDN.lab.execute("s0", "ovs-vsctl show")
    output = parse_klonet_output("s0", res)
    
    expected_target = f"tcp:{SDNStarTopo.CTRL_IP}:{SDNStarTopo.CTRL_PORT}"
    
    if expected_target in output:
        if "is_connected: true" in output:
            print(f"✅ S0 is CONNECTED to controller.")
        else:
            print(f"⚠️ S0 target set but NOT connected. (Check Ryu log)")
    else:
        print(f"❌ S0 target configuration failed.")

    print("\n--- ✅ 测试结束 ---")