from .base_api import KlonetBaseAPI
from typing import List, Optional, Dict, Any
import json
import time
import re

class KlonetSDNAPI(KlonetBaseAPI):
    """
    Klonet SDN 实验接口类 (Ryu + OpenFlow).
    解决 OVS Secure 模式下清空流表导致网络无法自愈的问题。

    该类封装了与 Ryu 控制器及 OpenFlow 交换机交互的常用操作。
    适用于故障注入、流表操纵及状态监控。
    """

    # --- Ryu 控制器管理 ---
    def ryu_start_manager(self, device_name: str, apps: List[str], log_file: str = "/tmp/ryu.log") -> str:
        """
        启动 Ryu 控制器。
        
        Args:
            device_name: 节点名称 (如 "controller")
            apps: Ryu App 列表 (如 ["ryu.app.simple_switch_13"])
            log_file: 日志路径
        """
        app_str = " ".join(apps)
        # 强制使用 python3 启动
        command = f"nohup python3 -m ryu.cmd.manager --verbose {app_str} > {log_file} 2>&1 &"
        return self._run_cmd(device_name, command)

    def ryu_stop_manager(self, device_name: str) -> str:
        """停止 Ryu 控制器进程 (pkill)。"""
        return self._run_cmd(device_name, "pkill -9 -f ryu-manager")

    def ryu_check_status(self, device_name: str) -> Dict[str, bool]:
        """
        检查 Ryu 服务状态。
        Returns:
            dict: {"process": bool, "of_port": bool, "rest_port": bool}
        """
        res = self._run_cmd(device_name, "netstat -tulnp")
        return {
            "process": "ryu-manager" in res or "python" in res,
            "of_port": "6633" in res or "6653" in res,
            "rest_port": "8080" in res
        }

    # --- OVS 精确操作 (核心修复) ---
    def local_inject_drop(self, switch_node: str):
        """
        [核心] 在 init-br0 上强制插入 DROP 流表
        """
        bridge = "init-br0"
        print(f"    🔒 [Lockdown] 正在封锁节点 {switch_node} 的 {bridge}...")
        
        # 1. 确保协议版本正确
        self._run_cmd(switch_node, f"ovs-vsctl set bridge {bridge} protocols=OpenFlow13")
        
        # [修复点 1] 不要执行 del-flows！
        # 如果在这里清空流表，会把 Table-Miss (连接控制器的通道) 也删掉。
        # 我们直接利用 Priority 机制覆盖。
        # self._run_cmd(switch_node, f"ovs-ofctl -O OpenFlow13 del-flows {bridge}")
        
        # 2. 写入最高优先级 DROP 规则 (Priority=60000)
        # 这条规则会压制住底下的 Priority=0 (Controller) 和 Priority=1 (Forwarding)
        cmd = f"ovs-ofctl -O OpenFlow13 add-flow {bridge} \"priority=60000,table=0,actions=drop\""
        self._run_cmd(switch_node, cmd)
        
        # 3. 验证流表是否写入成功
        verify = self._run_cmd(switch_node, f"ovs-ofctl -O OpenFlow13 dump-flows {bridge}")
        if "priority=60000" in verify and "drop" in verify:
            print(f"      ✅ 流表写入确认: Priority 60000 DROP 已生效")
        else:
            print(f"      ❌ 流表写入失败！当前流表:\n{verify}")
            raise Exception(f"无法在 {switch_node} 上写入阻断流表")

    def local_clear_drop(self, switch_node: str):
        """
        [核心修复] 恢复环境
        不能使用 del-flows 清空所有，否则在 Secure 模式下会断开与控制器的联系。
        必须使用 --strict 精确删除 DROP 规则，并确保 Table-Miss 存在。
        """
        bridge = "init-br0"
        print(f"    🔓 [Restore] 正在恢复节点 {switch_node}...")

        # [修复点 2] 使用 --strict 精确删除 Priority 60000 的规则
        # 这样不会误伤 Priority 0 的控制器连接规则
        cmd_del = f"ovs-ofctl -O OpenFlow13 --strict del-flows {bridge} priority=60000"
        self._run_cmd(switch_node, cmd_del)

        # [修复点 3] 保险机制：重新补发 Table-Miss 规则
        # 万一之前的操作意外删除了基础规则，这里补上一条 "兜底规则"
        # 含义：所有不匹配的包，发给控制器 (Packet-In)
        cmd_ensure_ctrl = f"ovs-ofctl -O OpenFlow13 add-flow {bridge} \"priority=0,actions=CONTROLLER:65535\""
        self._run_cmd(switch_node, cmd_ensure_ctrl)

    # --- 诊断工具 ---
    def check_ping(self, src_node: str, target_ip: str, count: int = 2) -> bool:
        """
        执行 Ping 测试并返回布尔值结果。
        """        
        res = self._run_cmd(src_node, f"ping -c {count} -W 1 {target_ip}")
        # 只要没有 100% packet loss 就算通
        return "bytes from" in res and "100% packet loss" not in res

    def check_interface_ip(self, node: str) -> str:
        """
        查看 IP 和接口
        """        
        return self._run_cmd(node, "ip addr show")

if __name__ == "__main__":
    print("\n🚀 ======= SDN 实验环境精确修复版 (Target: init-br0) =======")
    
    LAB_NAME = "sdn_openflow_test"
    CTRL_NODE = "controller"
    TARGET_SWITCHES = ["s1", "s2", "s3"] 
    TEST_HOST_SRC = "h1"
    TEST_HOST_DST_IP = "10.0.0.2"
    
    api = KlonetSDNAPI(LAB_NAME)

    try:
        # --- Step 1: 启动控制器 ---
        print("\n[Step 1] 重启控制器...")
        api.ryu_stop_manager(CTRL_NODE)
        time.sleep(1)
        api.ryu_start_manager(CTRL_NODE, ["ryu.app.simple_switch_13", "ryu.app.ofctl_rest"])
        print("  ⏳ 等待 OVS 连接 (8s)...")
        time.sleep(8)
        
        # --- Step 2: 基准测试 ---
        print("\n[Step 2] 基准连通性测试...")
        api._run_cmd(TEST_HOST_SRC, f"ping -c 2 {TEST_HOST_DST_IP}")
        if api.check_ping(TEST_HOST_SRC, TEST_HOST_DST_IP):
            print("  ✅ 基准状态正常：网络畅通。")
        else:
            print("  ⚠️ 尝试激活网络...")
            api._run_cmd(TEST_HOST_SRC, "ping -c 1 -b 10.0.0.255")
            time.sleep(2)
            if not api.check_ping(TEST_HOST_SRC, TEST_HOST_DST_IP):
                print(f"  ❌ 错误: 实验开始前 Ping 不通。")
                print("  诊断信息 (h1 IP):")
                print(api.check_interface_ip(TEST_HOST_SRC))

        # --- Step 3: 故障注入 ---
        print("\n[Step 3] 注入故障: 封锁 init-br0...")
        for sw in TARGET_SWITCHES:
            api.local_inject_drop(sw)
        
        time.sleep(1)

        # 验证
        print("  🧪 验证故障效果 (Expect Ping Fail)...")
        ping_res = api._run_cmd(TEST_HOST_SRC, f"ping -c 3 -W 1 {TEST_HOST_DST_IP}")
        
        if "100% packet loss" in ping_res:
            print("  ✅ Ping 已中断！(故障注入成功)")
            print("     [Log] 丢包确认: 100% packet loss")
        elif "bytes from" in ping_res:
            print("  ❌ 严重失败: Ping 依然通畅。")
            raise Exception("流表已写入但未生效")
        else:
            print("  ✅ Ping 中断 (无回显)。")

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")

    finally:
        print("\n[Step 4] 还原环境...")
        print("  🧹 清除阻断规则并修复控制器连接...")
        for sw in TARGET_SWITCHES:
            api.local_clear_drop(sw)
        
        print("  🔄 触发网络自愈 (ARP Request)...")
        time.sleep(2)
        # 发送 Ping 触发 ARP 学习
        api._run_cmd(TEST_HOST_SRC, f"ping -c 1 {TEST_HOST_DST_IP}")
        
        if api.check_ping(TEST_HOST_SRC, TEST_HOST_DST_IP):
             print("  ✅ 网络自愈成功！")
        else:
             print("  ⚠️ 网络恢复中，再次尝试...")
             time.sleep(2)
             if api.check_ping(TEST_HOST_SRC, TEST_HOST_DST_IP):
                 print("  ✅ 网络自愈成功 (第二次尝试)。")
             else:
                 print("  ❌ 网络恢复失败。请检查 Table-Miss 流表是否丢失。")
                 print("  Debug (s1 flow):")
                 print(api._run_cmd("s1", "ovs-ofctl -O OpenFlow13 dump-flows init-br0"))

    print("\n======= 测试结束 =======")