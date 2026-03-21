import asyncio
import sys
import os
import time
import json
import subprocess

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
playground_dir = os.path.abspath(os.path.join(current_dir, "../../../src/playground"))

if playground_dir not in sys.path:
    sys.path.insert(0, playground_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 导入底层组件
from fault_injector.fault_inject_pool import FaultInjector, HOST_INJECT_INPUT
from service.klonet.base_api import KlonetBaseAPI 
from src.agent.react_agent import NetworkFaultDiagnosisAgent
from utils.logger import system_logger

logger = system_logger

# ==========================================
# 辅助函数: 精简拓扑信息算法 (核心重写)
# ==========================================
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
            
            # 格式化接口 (修复接口命名逻辑)
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')
                
                # --- 核心修改：修正接口名称 ---
                # 如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname
                # ------------------------------

                if ip:
                    iface_strs.append(f"{actual_iname}({ip})")
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


# ==========================================
# 辅助函数: 生成自然语言故障描述
# ==========================================
def generate_problem_info(fault_name: str, cfg: dict) -> str:
    if "link" in fault_name:
        return f"用户投诉: 主机 {cfg.get('host')} 访问 {cfg.get('peer_host')} 时，链路出现严重网络卡顿、延迟极高或丢包等现象。"
    elif "host" in fault_name or fault_name in ["inject_interface_down", "inject_ip_misconfig", "inject_default_route_missing", "inject_arp_poisoning", "inject_dns_error", "inject_high_cpu_load"]:
        target = cfg.get("target")
        peer = cfg.get("peer_ip_cross_subnet")
        if "dns" in fault_name:
            return f"用户投诉: 主机 {target} 无法访问百度网，但通过 IP 似乎可以连通其他节点。"
        elif "cpu" in fault_name:
            return f"用户投诉: 主机 {target} 可以连通，但延迟不稳定。"
        return f"用户投诉: 主机 {target} 无法正常 Ping 通节点 {peer}，网络完全不可达。"
    elif "ovs" in fault_name or "sdn" in fault_name:
        return f"用户投诉: SDN网络瘫痪，主机 {cfg.get('host_src')} 发往 {cfg.get('dst_ip')} 的新流量被全部丢弃。"
    elif "bmv2" in fault_name or "p4" in fault_name:
        return f"用户投诉: 途径 P4 交换机的数据包发生异常，主机 {cfg.get('host_src')} 无法联通 {cfg.get('host_dst')} 和特定 IP {cfg.get('drop_ip')}。"
    elif "ospf" in fault_name:
        return f"用户投诉: 主机 {cfg.get('host_src')} 刚刚无法正常 Ping 通节点 {cfg.get('dst_ip')}，网络完全不可达，疑似路由问题。"
    else:
        return f"用户投诉: 主机 {cfg.get('host_src')} 无法正常 Ping 通节点 {cfg.get('dst_ip')}，网络完全不可达，疑似路由问题。"


# ==========================================
# 核心测试流
# ==========================================
def run_agent_test_case(lab_name: str, fault_name: str, expected_root_cause: str, cfg: dict):

    # 核心修复：强制将当前的 lab_name 写入环境变量！
    # 这样底层所有 MCP Server 在执行 os.getenv("LAB_NAME") 时拿到的都是正确的值
    os.environ["LAB_NAME"] = lab_name

    print(f"\n{'='*50}")
    print(f"🚀 测试用例: [{fault_name}] -> 预期: [{expected_root_cause}]")
    print(f"{'='*50}")
    
    inj_pool = FaultInjector(lab_name)
    
    try:
        # 0. 创建拓扑
        print(f"[System] 🛠️  正在部署网络拓扑 ({lab_name} via {lab_name}.py)...")
        cmd = ["uv", "run", f"{lab_name}.py"]
        cwd = "/home/lzl/tmx/PlayGround/src/net_env"
        
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Error] ❌ 拓扑部署失败:\n{result.stderr}")
        
        print(f"[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...")
        time.sleep(4)

        # 1. 获取全量拓扑 JSON 并过滤
        logger.info("Fetching and simplifying topology...")
        api = KlonetBaseAPI(lab_name)
        # 获取底层平台字典 (如果你底层不是字典而是文本，请用 json.loads 转换)
        raw_topo_dict = api.get_topo_json() 
        netenv_info = simplify_topo(lab_name, raw_topo_dict)
        
        # 2. 注入故障并生成描述
        logger.info(f"Injecting fault: {fault_name} ...")
        inj_pool.inject(fault_name)
        time.sleep(2)
        problem_info = generate_problem_info(fault_name, cfg)
        
        # 3. 运行 Agent
        agent = NetworkFaultDiagnosisAgent(
            lab_name=lab_name,
            max_steps=50,
            netenv_info=netenv_info, 
            problem_info=problem_info,
            backend_model="qwen3.5-27b"  # qwen3.5-27b, gemini-3-flash-preview
        )
        agent_result = asyncio.run(agent.run_diagnosis())
        
        # 4. 结果比对断言
        print(f"\n📊 [测试结果评估]")
        print(f"预期 Root Cause: {expected_root_cause}")
        print(f"Agent 诊断结论: {agent_result}")
        
        if expected_root_cause.strip().lower() == agent_result.strip().lower():
            print("✅ 测试通过 (PASS)")
        else:
            print("❌ 测试失败 (FAIL)")
            
    except Exception as e:
        logger.error(f"测试用例 {fault_name} 异常: {e}")

    finally:
        # 5. 销毁拓扑
        print(f"[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
        try:
            api = KlonetBaseAPI(lab_name)
            api.lab.reset_project()
            print("[System] ✅ 拓扑销毁成功。")
        except:
            pass
        time.sleep(3)

