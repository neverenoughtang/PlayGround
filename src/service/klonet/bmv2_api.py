from typing import List, Optional, Dict, Any, Union
import re
import time
import ipaddress

# --- [修复] 兼容 MCP 调用和直接运行 ---
try:
    # 尝试作为包内模块导入 (供 MCP 使用)
    from .base_api import KlonetBaseAPI
except ImportError:
    # 如果失败，说明是直接运行此脚本 (供调试使用)
    from base_api import KlonetBaseAPI

class KlonetBMv2API(KlonetBaseAPI):
    """
    Klonet BMv2 P4 交换机控制接口类 (CLI Wrapper + Smart Parsing).
    """

    def _exec_cli_cmd(self, node: str, cli_cmd: str) -> str:
        """底层核心：执行 CLI 命令"""
        full_cmd = f"bash -c 'echo \"{cli_cmd}\" | simple_switch_CLI --thrift-port 9090'"
        raw_output = self._run_cmd(node, full_cmd)
        
        clean_lines = []
        for line in raw_output.splitlines():
            line = line.strip()
            # 仅过滤极其确定的噪音，保留大部分内容以防误删
            if not line: continue
            if "Obtaining JSON" in line: continue
            if "Control utility" in line: continue
            
            # 处理 RuntimeCmd 前缀
            if "RuntimeCmd:" in line:
                content = line.replace("RuntimeCmd:", "").strip()
                if content: clean_lines.append(content)
            else:
                clean_lines.append(line)
        return "\n".join(clean_lines)

    # --- 基础查询 ---
    def bmv2_table_dump(self, node: str, table_name: str) -> str:
        return self._exec_cli_cmd(node, f"table_dump {table_name}")

    def bmv2_table_add(self, node: str, table_name: str, action_name: str, 
                       match_keys: List[str], action_params: List[str] = [], priority: int = 0) -> str:
        matches_str = " ".join(match_keys)
        params_str = " ".join(action_params)
        prio_str = f" {priority}" if priority > 0 else ""
        cmd = f"table_add {table_name} {action_name} {matches_str} => {params_str}{prio_str}"
        # print(f" ➕ [BMv2 CLI] {node}: {cmd}")
        return self._exec_cli_cmd(node, cmd)

    def bmv2_table_modify(self, node: str, table_name: str, action_name: str, 
                          entry_handle: int, action_params: List[str] = []) -> str:
        """
        [关键] 修改现有流表项的动作。
        修复版: 针对 runtime_CLI.py 的 IndexError Bug，强制添加 "=>" 后缀。
        """
        params_str = " ".join(action_params)
        
        # [Bug Fix] 
        # 某些版本的 runtime_CLI.py 在解析 table_modify 时有 Bug (IndexError: list index out of range)。
        # 它强制检查 args[3] == "=>"，如果只有 3 个参数(无参动作)就会崩溃。
        # 解决方法: 无论是否有参数，都显式加上 "=>"。
        cmd = f"table_modify {table_name} {action_name} {entry_handle} => {params_str}"
        
        # 去除可能多余的尾部空格
        cmd = cmd.strip()
        
        # print(f" 🔧 [BMv2 CLI] {node}: {cmd}")
        return self._exec_cli_cmd(node, cmd)

    # --- 智能解析工具 ---
    def ip_to_hex_str(self, ip_str: str) -> str:
        """
        辅助：将 10.0.0.2 转为 0a000002 (BMv2 CLI 格式，不带冒号)
        """
        try:
            # 移除 /32 等掩码
            ip = ip_str.split('/')[0]
            packed = ipaddress.IPv4Address(ip).packed
            # 格式化为无冒号的 hex 字符串
            return "".join(f"{b:02x}" for b in packed)
        except:
            return ip_str

    def get_handle_by_ip(self, node: str, table_name: str, ip_match: str) -> Optional[int]:
        """
        [终极逻辑] 查找 Handle ID
        """
        dump_out = self.bmv2_table_dump(node, table_name)
        
        # [DEBUG]
        # print(f"   🔎 [Debug Dump] Scanning table content...")

        # 准备匹配模式: 0a000002
        target_hex = self.ip_to_hex_str(ip_match).lower()
        
        current_handle = None
        
        for line in dump_out.splitlines():
            line = line.strip().lower()
            
            # 1. 抓取 Handle: "dumping entry 0x1"
            handle_match = re.search(r'dumping entry (0x[0-9a-f]+)', line)
            if handle_match:
                current_handle = int(handle_match.group(1), 16)
                continue
            
            # 2. 匹配 Key (只要当前有 Handle，且行内包含无冒号的 Hex 就算命中)
            if current_handle is not None:
                # 这里的逻辑是：只要行里出现了 '0a000002' 这一串字符
                if target_hex in line:
                    # print(f"   🎯 Match Found! Line: '{line}' -> Handle: {current_handle}")
                    return current_handle
        
        return None

# ==============================================================================
# 🎯 主函数测试 (智能故障注入)
# ==============================================================================

if __name__ == "__main__":
    print("\n🚀 ======= BMv2 智能故障注入测试 (Modify Mode) =======")
    
    LAB_NAME = "p4_star_test" 
    api = KlonetBMv2API(LAB_NAME)
    
    TARGET_SWITCH = "s1"
    TABLE_NAME = "MyIngress.ipv4_lpm"
    
    # 真实目标: 必须是当前能 Ping 通的那个 IP
    TARGET_IP_CIDR = "10.0.0.2/32" 
    SRC_HOST = "h1"
    TARGET_HOST_IP = "10.0.0.2"

    # 保存原始状态以便恢复
    original_action = "MyIngress.ipv4_forward"
    # 注意: 这里需要你手动填入或动态获取原始参数 (MAC, Port)
    # 根据你之前的 successful log: h2 -> b2:b2:36:cc:5c:90, Port 1
    # 这一步在自动化系统中可以先解析 dump 获取，这里为了演示直接硬编码恢复参数
    original_params = ["b2:b2:36:cc:5c:90", "1"] 

    try:
        # 1. 查找目标规则 Handle
        print(f"\n[Step 1] 寻找 {TARGET_IP_CIDR} 的现有规则...")
        handle = api.get_handle_by_ip(TARGET_SWITCH, TABLE_NAME, TARGET_IP_CIDR)
        
        if handle is None:
            print(f" ❌ 未找到 {TARGET_IP_CIDR} 的规则！无法进行修改注入。")
            print("    (请先运行 p4_star.py 确保环境是通的)")
            exit(1)
        print(f" ✅ 找到目标规则 Handle: {handle}")

        # 2. 基准测试
        print(f"\n[Step 2] 基准 Ping (Should PASS)...")
        if "0% packet loss" in api._run_cmd(SRC_HOST, f"ping -c 2 -W 1 {TARGET_HOST_IP}"):
            print(" ✅ 网络畅通。")
        else:
            raise Exception("实验前网络不通，请检查环境！")

        # 3. 注入故障 (Modify -> Drop)
        print(f"\n[Step 3] 💉 注入故障: 修改 Handle {handle} -> DROP")
        # 修改动作为 drop，参数为空
        res = api.bmv2_table_modify(TARGET_SWITCH, TABLE_NAME, "MyIngress.drop", handle, [])
        if "Error" in res:
            raise Exception(f"修改失败: {res}")
        print(" ✅ 动作已修改为丢弃。")

        # 4. 验证故障
        print(f"\n[Step 4] 🧪 验证故障 (Should FAIL)...")
        res_fail = api._run_cmd(SRC_HOST, f"ping -c 2 -W 1 {TARGET_HOST_IP}")
        if "100% packet loss" in res_fail:
            print(" ✅ 故障注入成功！Ping 已中断。")
        else:
            print(" ❌ 故障未生效！Ping 依然通畅。")

        # 5. 恢复环境 (Modify -> Forward)
        print(f"\n[Step 5] 🚑 恢复环境: Handle {handle} -> Forward")
        # 恢复原始动作和参数
        api.bmv2_table_modify(TARGET_SWITCH, TABLE_NAME, original_action, handle, original_params)
        
        # 6. 最终验证
        print(f"\n[Step 6] 回归测试 (Should PASS)...")
        time.sleep(1)
        if "0% packet loss" in api._run_cmd(SRC_HOST, f"ping -c 2 -W 1 {TARGET_HOST_IP}"):
            print(" ✅ 网络自愈成功。")
        else:
            print(" ❌ 恢复失败！")

    except Exception as e:
        print(f"\n❌ 异常中断: {e}")
        # 如果恢复失败，可能需要手动恢复，或者简单地重启 p4_star.py

    print("\n======= 测试结束 =======")