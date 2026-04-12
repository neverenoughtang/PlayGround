import asyncio
import sys
import os
import time
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
playground_dir = os.path.abspath(os.path.join(current_dir, "../../../src/playground"))
if playground_dir not in sys.path: sys.path.insert(0, playground_dir)
if project_root not in sys.path: sys.path.append(project_root)

from mcp_server.klonet_base_api import KlonetBaseAPI 
from src.agent.fault_inject_agent import FaultInjectAgent


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
                netmask = iface.get('netmask', '/24') 
                mask = f"/{sum(bin(int(x)).count('1') for x in netmask.split('.'))}" # 掩码

                # --- 核心修改：修正接口名称 ---
                # 如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname
                # ------------------------------

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


def run_injection_only_test(lab_name: str, fault_query: str):
    """
    极简测试流：仅测试网络部署与智能体自动注入功能。
    """
    os.environ["LAB_NAME"] = lab_name

    print(f"\n{'='*60}")
    print(f"🚀 纯注入测试启动 | 场景: [{lab_name}]")
    print(f"🗣️ 注入指令: {fault_query}")
    print(f"{'='*60}")
    
    try:
        # 1. 创建拓扑
        print(f"[System] 🛠️ 正在部署网络拓扑 ({lab_name}.py)...")
        cmd = ["uv", "run", f"{lab_name}.py"]
        cwd = os.path.abspath(os.path.join(current_dir, "../../../src/net_env"))
        
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Error] ❌ 拓扑部署失败:\n{result.stderr}")
            return
        
        print(f"[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...")
        time.sleep(4)

        # 2. 获取并精简拓扑
        api = KlonetBaseAPI(lab_name)
        raw_topo_dict = api.get_topo_json() 
        netenv_info = simplify_topo(lab_name, raw_topo_dict)
        
        # 3. 让注入智能体全权接管：检索知识库 -> 生成脚本 -> 注入验证 -> 返回描述
        print(f"\n[System] 🤖 移交控制权给 FaultInjectAgent...")
        agent = FaultInjectAgent(
            lab_name=lab_name,
            max_steps=50, 
            netenv_info=netenv_info, 
            fault_query=fault_query,
            backend_model="qwen3.5-27b" 
        )
        
        agent_result = asyncio.run(agent.inject_check_fault())
        
        # 4. 打印智能体反馈的信息
        print(f"\n📊 [注入智能体成果汇报]")
        print(f"执行结果: {agent_result['inject_result']}")
        print(f"预期故障名称 (传给后续裁判): {agent_result['expected_fault']}")
        print(f"自动生成的故障表现 (传给诊断 Agent):\n{agent_result['fault_description']}")
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")

    finally:
        # 5. 销毁拓扑
        print(f"\n[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
        try:
            api = KlonetBaseAPI(lab_name)
            api.lab.reset_project()
            print("[System] ✅ 拓扑销毁成功。")
        except:
            pass
        time.sleep(3)