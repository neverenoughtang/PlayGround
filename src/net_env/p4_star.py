import re
import os
from dotenv import load_dotenv
load_dotenv() 
import time
import logging
import subprocess

from KlonetAPI import *
from base_netenv import NetworkEnvBase

# 辅助解析函数
def safe_parse(response):
    if isinstance(response, str): return response
    if isinstance(response, dict):
        if 'output' in response: return response['output']
        for v in response.values():
            res = safe_parse(v)
            if res: return res
    return str(response)

class P4StarTopo(NetworkEnvBase):
    """
    P4 场景: 星型拓扑 (Star) - 适配 new_bmv2 镜像
    
    拓扑结构:
           S1 (BMv2)
          |  |  |  |
        H1  H2  H3  H4
    
    变更说明:
    - BMv2 启动逻辑已移除，下沉至 klonet.py 的 p4_config() 中。
    - 修复验证逻辑，防止 Docker 管理网段造成的连通性误报。
    """
    
    def __init__(self, lab_name="p4_star"):
        super().__init__(lab_name=lab_name)
        # 1. 创建节点
        self.s1 = self.lab.add_node("s1", self.lab.images["new_bmv2"], x=400, y=300)
        self.h1 = self.lab.add_node("h1", self.lab.images["ubuntu"], x=200, y=100)
        self.h2 = self.lab.add_node("h2", self.lab.images["ubuntu"], x=600, y=100)
        self.h3 = self.lab.add_node("h3", self.lab.images["ubuntu"], x=200, y=500)
        self.h4 = self.lab.add_node("h4", self.lab.images["ubuntu"], x=600, y=500)

        # 2. 创建链路
        self.lab.add_link(self.s1, self.h1)
        self.lab.add_link(self.s1, self.h2)
        self.lab.add_link(self.s1, self.h3)
        self.lab.add_link(self.s1, self.h4)

        # 3. 部署
        print("Deploying topology...")
        self.deploy()
        print("Waiting 15s for stabilization...")
        time.sleep(15)

        # 4. 基础配置 (只配 IP，不启动 switch)
        self.config(senario="p4")
        
        # 5. [核心] 冷启动模式部署
        self.deploy_and_start_switch()
        
        print("P4 Topology Ready.")

    def get_host_mac(self, node_name):
        res = self.lab.execute(node_name, "ip -o link show")
        output = safe_parse(res)
        for line in output.splitlines():
            if "lo:" in line or "loopback" in line: continue
            match = re.search(r'link/ether\s+([0-9a-fA-F:]{17})', line)
            if match: return match.group(1)
        return None

    def deploy_and_start_switch(self):
        print("\n>>> [Surgical] Starting Cold-Boot Deployment...")
        
        s1_name = "s1"
        target_p4_file = "/tmp/basic.p4"
        json_file = "/tmp/basic.json"
        log_file = "/tmp/bmv2.log"
        local_p4_file = "resource/p4_star_code.p4"

        # 1. 上传
        print(f"  1. Uploading P4 Source...")
        if not os.path.exists(local_p4_file):
            print(f"❌ Error: {local_p4_file} missing!")
            return
        with open(local_p4_file, 'r') as f: content = f.read()
        escaped = content.replace('"', '\\"').replace('`', '\\`')
        self.lab.execute(s1_name, f"bash -c 'cat <<EOF > {target_p4_file}\n{escaped}\nEOF'")

        # 2. 编译
        print(f"  2. Compiling to JSON...")
        res = self.lab.execute(s1_name, f"bash -c 'p4c-bm2-ss --p4v 16 --std p4-16 -o {json_file} {target_p4_file}'")
        if "error" in safe_parse(res).lower():
            print(f"❌ Compile Error: {safe_parse(res)}")
            return
        print("     ✅ Compiled successfully.")

        # 3. 冷启动
        print(f"  3. Cold Booting Switch...")
        self.lab.execute(s1_name, "bash -c 'pkill -9 simple_switch'")
        time.sleep(1)
        
        find_cmd = "ip -o link show | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -v -E 'lo|tun|eth0' | sort | tr '\n' ' '"
        raw_res = self.lab.execute(s1_name, f"bash -c \"{find_cmd}\"")
        ifaces = safe_parse(raw_res).strip().split()
        print(f"     Binding interfaces: {ifaces}")
        
        iface_args = ""
        for idx, iface in enumerate(ifaces):
            iface_args += f"-i {idx}@{iface} "

        start_cmd = (
            f"nohup simple_switch {iface_args} "
            f"--thrift-port 9090 "
            f"--log-console "
            f"{json_file} "
            f"> {log_file} 2>&1 & sleep 2"
        )
        self.lab.execute(s1_name, f"bash -c '{start_cmd}'")
        
        pid_res = self.lab.execute(s1_name, "bash -c 'pgrep -x simple_switch'")
        if not safe_parse(pid_res).strip():
            print("❌ Start Failed! Log:")
            print(safe_parse(self.lab.execute(s1_name, f"cat {log_file}")))
            return
        print("     ✅ Switch Started with P4 Logic!")

        # 4. 自动发现表名 & 下发流表
        print(f"  4. Populating Tables...")
        
        res_tables = self.lab.execute(s1_name, f"bash -c 'echo show_tables | simple_switch_CLI --thrift-port 9090'")
        tables_out = safe_parse(res_tables)
        
        real_table_name = None
        for line in tables_out.splitlines():
            if "ipv4_lpm" in line:
                parts = line.split()
                for part in parts:
                    if "ipv4_lpm" in part and "RuntimeCmd" not in part:
                        real_table_name = part.strip()
                        break
            if real_table_name: break
        
        if not real_table_name:
            print(f"❌ Error: 'ipv4_lpm' table not found. Dump:\n{tables_out}")
            return
        print(f"     Target Table: {real_table_name}")

        host_map = {
            "h1": {"port": 0, "ip": "10.0.0.1"},
            "h2": {"port": 1, "ip": "10.0.0.2"},
            "h3": {"port": 2, "ip": "10.0.0.3"},
            "h4": {"port": 3, "ip": "10.0.0.4"}
        }

        cli_commands = []
        for name, info in host_map.items():
            info["mac"] = self.get_host_mac(name)
            cli_commands.append(f"table_add {real_table_name} ipv4_forward {info['ip']}/32 => {info['mac']} {info['port']}")
            
            for neighbor in host_map:
                if neighbor == name: continue
                self.lab.execute(neighbor, f"bash -c 'arp -s {info['ip']} {info['mac']}'")

        # 使用文件批处理下发
        full_cmd_content = "\n".join(cli_commands)
        cmd_file = "/tmp/runtime_cmds.txt"
        self.lab.execute(s1_name, f"bash -c 'cat <<EOF > {cmd_file}\n{full_cmd_content}\nEOF'")
        res_rules = self.lab.execute(s1_name, f"bash -c 'simple_switch_CLI --thrift-port 9090 < {cmd_file}'")
        
        if "Error" in safe_parse(res_rules):
            print(f"❌ Rule Error:\n{safe_parse(res_rules)}")
        else:
            print("     ✅ Rules & ARP Populated.")

if __name__ == "__main__":
    Lab = P4StarTopo()
    
    print("\n--- 🔍 终极真相 (The Moment of Truth) ---")
    
    # 1. 验证流表
    print("1. Checking Table Entries...")
    dump_res = Lab.lab.execute("s1", "bash -c 'echo table_num_entries MyIngress.ipv4_lpm | simple_switch_CLI --thrift-port 9090'")
    print(f"   Response: {safe_parse(dump_res).strip()}")

    # 2. 启动抓包 (H2 监听)
    print("\n2. Starting Tcpdump on H2 (Background)...")
    # 抓取来自 H1 (10.0.0.1) 的 ICMP 包
    sniffer_file = "/tmp/h2_sniff.log"
    Lab.lab.execute("h2", f"bash -c 'nohup tcpdump -i any src 10.0.0.1 -c 1 -n > {sniffer_file} 2>&1 &'")

    # 3. 真实 Ping
    print("\n3. Pinging H1 -> H2...")
    ping_res = Lab.lab.execute("h1", "ping -c 3 -W 1 10.0.0.2")
    output = safe_parse(ping_res)
    print(output)
    
    # 4. 检查抓包结果
    print("\n4. Checking H2 Sniffer Log...")
    sniff_res = Lab.lab.execute("h2", f"cat {sniffer_file}")
    sniff_out = safe_parse(sniff_res)
    print(f"   [H2 Tcpdump]: {sniff_out.strip()}")

    # 5. 综合判定
    success = False
    if re.search(r'(?<!\d)0% packet loss', output):
        print("\n🎉🎉🎉 SUCCESS! Ping Passed! 🎉🎉🎉")
        success = True
    elif "ICMP echo request" in sniff_out:
        print("\n⚠️  Ping Failed, BUT H2 received the packet!")
        print("   -> Reason: Likely a Checksum Error or Checksum Offload issue.")
        print("   -> Your P4 switch IS working, but Linux Kernel is dropping bad packets.")
        print("   -> Fix: Ensure 'MyComputeChecksum' is correctly implemented in P4.")
    else:
        print("\n❌ Ping Failed and H2 received NOTHING.")
        print("   -> Reason: Packet dropped inside the switch.")