import re
import os
import sys
from dotenv import load_dotenv
load_dotenv() 
import time
import subprocess

from KlonetAPI import *
from base_netenv import NetworkEnvBase

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)

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
    P4 场景: 星型拓扑 (规模扩容) - 1 Switch, 12 Hosts
    """
    def __init__(self, lab_name="p4_star"):
        super().__init__(lab_name=lab_name)
        # 1. 创建节点
        self.s1 = self.lab.add_node("s1", self.lab.images["new_bmv2"], x=400, y=300)
        self.hosts = [self.lab.add_node(f"h{i}", self.lab.images["new_ubuntu"], x=100+50*i, y=100 if i%2==0 else 500) for i in range(1, 13)]

        # 2. 创建链路
        for h in self.hosts:
            self.lab.add_link(self.s1, h)

        # 3. 部署
        print("Deploying topology...")
        self.deploy()
        print("Waiting 15s for stabilization...")
        time.sleep(15)

        # 4. 基础配置
        self.config(senario="p4")
        
        # 5. 冷启动模式部署
        self.deploy_and_start_switch()
        print("P4 Topology Ready.")

    def get_host_data_info(self, node_name):
        """
        【最核心的修复】：精准提取数据网卡的 IP 和 MAC，防 Docker eth0 干扰！
        """
        # 提取 Data IP (排除 lo 和 eth0)
        ip_res = safe_parse(self.lab.execute(node_name, "ip -o -4 addr show")).splitlines()
        data_ip = None
        iface_name = None
        
        for line in ip_res:
            if " lo " in line or " eth0 " in line: continue
            # 格式例如: 2: tos1_1    inet 10.0.0.4/24 ...
            parts = line.split()
            if len(parts) >= 4:
                iface_name = parts[1]
                data_ip = parts[3].split('/')[0] # 去掉 /24
                break
        
        # 提取真实 Data MAC
        data_mac = None
        if iface_name:
            mac_res = safe_parse(self.lab.execute(node_name, f"ip -o link show {iface_name}"))
            match = re.search(r'link/ether\s+([0-9a-fA-F:]{17})', mac_res)
            if match: data_mac = match.group(1)
            
        return data_ip, data_mac

    def deploy_and_start_switch(self):
        print("\n>>> [Surgical] Starting Cold-Boot Deployment...")
        s1_name = "s1"
        target_p4_file = "/tmp/basic.p4"
        json_file = "/tmp/basic.json"
        log_file = "/tmp/bmv2.log"
        local_p4_file = "resource/p4_star_code.p4"

        print(f"  1. Uploading P4 Source...")
        with open(local_p4_file, 'r') as f: content = f.read()
        escaped = content.replace('"', '\\"').replace('`', '\\`')
        self.lab.execute(s1_name, f"bash -c 'cat <<EOF > {target_p4_file}\n{escaped}\nEOF'")

        print(f"  2. Compiling to JSON...")
        self.lab.execute(s1_name, f"bash -c 'p4c-bm2-ss --p4v 16 --std p4-16 -o {json_file} {target_p4_file}'")

        print(f"  3. Cold Booting Switch...")
        self.lab.execute(s1_name, "bash -c 'pkill -9 simple_switch'")
        time.sleep(1)
        
        find_cmd = "ip -o link show | awk -F': ' '{print $2}' | cut -d@ -f1 | grep -v -E 'lo|tun|eth0' | sort | tr '\n' ' '"
        raw_res = self.lab.execute(s1_name, f"bash -c \"{find_cmd}\"")
        ifaces = safe_parse(raw_res).strip().split()
        
        # 动态绑定物理端口号
        port_mapping = {}
        iface_args = ""
        for idx, iface in enumerate(ifaces):
            iface_args += f"-i {idx}@{iface} "
            match = re.search(r'to(h\d+)_', iface)
            if match:
                port_mapping[match.group(1)] = idx

        start_cmd = f"nohup simple_switch {iface_args} --thrift-port 9090 --log-console {json_file} > {log_file} 2>&1 & sleep 2"
        self.lab.execute(s1_name, f"bash -c '{start_cmd}'")
        
        print(f"  4. Populating Tables...")

        # 构建真实的 Host Map
        host_map = {}
        for i in range(1, 13):
            h_name = f"h{i}"
            if h_name not in port_mapping:
                print(f"❌ [Error] 无法找到 {h_name} 对应的交换机物理端口！")
                continue
                
            dip, dmac = self.get_host_data_info(h_name)
            if not dip or not dmac:
                print(f"❌ [Error] 无法获取 {h_name} 的真实业务 IP/MAC！")
                continue
                
            host_map[h_name] = {
                "port": port_mapping[h_name],
                "ip": dip,
                "mac": dmac
            }

        cli_commands = []
        for name, info in host_map.items():
            # 👇【修复 1】：强制使用 MyIngress.ipv4_forward 全名，防止 CLI 拒收！
            cli_commands.append(f"table_add MyIngress.ipv4_lpm MyIngress.ipv4_forward {info['ip']}/32 => {info['mac']} {info['port']}")
            
            for neighbor in host_map:
                if neighbor == name: continue
                # 注入静态 ARP
                self.lab.execute(neighbor, f"bash -c 'arp -s {info['ip']} {info['mac']}'")

        # 👇【修复 2】：使用 Base64 无损写入命令文件，彻底规避 Bash 的 \n 换行符吞噬问题！
        import base64
        cmd_str = "\n".join(cli_commands) + "\n"
        b64_cmds = base64.b64encode(cmd_str.encode('utf-8')).decode('utf-8')
        
        cmd_file = "/tmp/runtime_cmds.txt"
        self.lab.execute(s1_name, f"bash -c 'echo {b64_cmds} | base64 -d > {cmd_file}'")
        
        # 抛给 P4 CLI 执行并打印回显
        res_rules = self.lab.execute(s1_name, f"bash -c 'simple_switch_CLI --thrift-port 9090 < {cmd_file}'")
        
        # 校验写入结果
        out_str = safe_parse(res_rules)
        if "Invalid action name" in out_str or "Error" in out_str:
            print(f"❌ [Fatal] 流表写入被 BMv2 拒绝！原因:\n{out_str}")
        else:
            print("     ✅ Rules & ARP Populated. (流表下发成功！)")


if __name__ == "__main__":
    Lab = P4StarTopo()
    
    print("\n" + "="*50)
    print(" 🛠️  保姆级深度检验 (Nanny-Level Diagnostics) ")
    print("="*50)
    
    # 1. 验证真实提取出的 IP/MAC
    h1_ip, h1_mac = Lab.get_host_data_info("h1")
    h12_ip, h12_mac = Lab.get_host_data_info("h12")
    print(f"[*] H1 真实网络数据 : IP={h1_ip} | MAC={h1_mac}")
    print(f"[*] H12真实网络数据 : IP={h12_ip} | MAC={h12_mac}")

    # 2. 窥探 P4 交换机里的转发表
    print("\n[*] 查看 S1 内部 P4 流表规则 (ipv4_lpm)...")
    dump_res = Lab.lab.execute("s1", "bash -c 'echo table_dump MyIngress.ipv4_lpm | simple_switch_CLI --thrift-port 9090'")
    print("\n".join([line for line in safe_parse(dump_res).splitlines() if "=>" in line])) # 只打核心规则

    # 3. 窥探 H1 的 ARP 缓存
    print("\n[*] 查看 H1 主机的 ARP 表...")
    arp_res = Lab.lab.execute("h1", "arp -n")
    print(safe_parse(arp_res).strip())

    # 4. 在 H12 开启上帝视角抓包
    print(f"\n[*] 在 H12 后台开启 Tcpdump 抓取来自 {h1_ip} 的包...")
    sniffer_file = "/tmp/h12_sniff.log"
    Lab.lab.execute("h12", f"bash -c 'nohup tcpdump -i any src {h1_ip} -c 2 -n > {sniffer_file} 2>&1 &'")
    time.sleep(1) # 等待抓包程序启动

    # 5. 见证奇迹的时刻
    print(f"\n[*] 发起世纪 Ping：H1 -> H12 ({h12_ip})...")
    ping_res = Lab.lab.execute("h1", f"ping -c 3 -W 1 {h12_ip}")
    output = safe_parse(ping_res)
    print(output)
    
    print("\n[*] 解析 H12 的抓包日志...")
    sniff_out = safe_parse(Lab.lab.execute("h12", f"cat {sniffer_file}"))
    print(sniff_out.strip() if sniff_out.strip() else "(空 - H12连个毛都没收到)")

    print("\n" + "="*50)
    print(" 💡 最终诊断结论 ")
    print("="*50)
    if re.search(r'(?<!\d)0% packet loss', output):
        print("🎉 完美！零丢包！P4 数据面路由规则天衣无缝！")
    elif "ICMP echo request" in sniff_out:
        print("⚠️ H12 收到了请求，但包被 Linux 内核丢了！(很可能是 P4 没有重算 Checksum，或 H12 缺少回程静态 ARP)")
    else:
        print("❌ 彻底死掉，包在 P4 交换机里神秘失踪，请检查上面的 P4 流表是否匹配了 IP！")