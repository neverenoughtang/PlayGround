import asyncio
import datetime
import sys
import os
import time
import subprocess
from dotenv import load_dotenv

load_dotenv()

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
playground_dir = os.path.abspath(os.path.join(current_dir, "../src/playground"))

if playground_dir not in sys.path:
    sys.path.insert(0, playground_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 导入底层组件
from fault_injector.fault_inject_pool import FaultInjector, HOST_INJECT_INPUT, LINK_INJECT_INPUT, SERVICE_INJECT_INPUT  
from service.klonet.base_api import KlonetBaseAPI 
from agent.main import build_agent_graph

# ==========================================
# 辅助函数: 精简拓扑信息算法
# ==========================================
def simplify_topo(lab_name: str, raw_topo: dict) -> str:
    simplified = []
    simplified.append(f"\n {lab_name} 的拓扑信息:")
    simplified.append("\n[节点列表]")
    categories = ['controllers', 'hosts', 'routers', 'switches', 'dpdks']
    for category in categories:
        if category not in raw_topo or not raw_topo[category]:
            continue
        for node_name, node_info in raw_topo[category].items():
            node_type = node_info.get('type', category)
            gateway = node_info.get('gateway', '')
            interfaces = node_info.get('interfaces', [])
            
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname
                if ip:
                    iface_strs.append(f"{actual_iname}({ip})")
                else:
                    iface_strs.append(f"{actual_iname}")
            
            info_str = f"- {node_name} [{node_type}]"
            if iface_strs: info_str += f" | 接口: {', '.join(iface_strs)}"
            if gateway: info_str += f" | 默认网关: {gateway}"
            simplified.append(info_str)
            
    simplified.append("\n[链路]")
    links = raw_topo.get('links', {})
    for link_name, link_info in links.items():
        src, src_ip = link_info.get('source', ''), link_info.get('sourceIP', '')
        tgt, tgt_ip = link_info.get('target', ''), link_info.get('targetIP', '')
        src_ip_clean = src_ip.split('/')[0] if src_ip else ""
        tgt_ip_clean = tgt_ip.split('/')[0] if tgt_ip else ""
        src_str = f"{src}({src_ip_clean})" if src_ip_clean else src
        tgt_str = f"{tgt}({tgt_ip_clean})" if tgt_ip_clean else tgt
        simplified.append(f"- 链路 {link_name}: {src_str} <---> {tgt_str}")
        
    return "\n".join(simplified)

# ==========================================
# 辅助函数: 故障描述
# ==========================================
def generate_problem_info(fault_name: str, cfg: dict) -> str:
    if "link" in fault_name:
        return f"用户投诉: 主机 {cfg.get('host')} 访问 {cfg.get('peer_host')} 时，链路出现严重网络卡顿、延迟极高或丢包等现象。"
    elif "host" in fault_name or fault_name in ["interface_down", "ip_misconfig", "default_route_missing", "arp_poisoning", "dns_error", "high_cpu_load"]:
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


CATE_TABLE = {
    "host": HOST_INJECT_INPUT,
    "link": LINK_INJECT_INPUT,
    "service": SERVICE_INJECT_INPUT
}

# ==========================================
# 核心: 测试场
# ==========================================
class Orchestrator:
    def __init__(self, react_llm: str = "qwen3.5-27b", judge_llm: str = "qwen3.5-27b"):
        self.actor_model = react_llm
        self.judge_model = judge_llm
        default_results_dir = os.path.abspath(os.path.join(current_dir, "../results"))
        self.results_dir = os.getenv("RESULTS_DIR", default_results_dir)
        os.makedirs(self.results_dir, exist_ok=True)

    async def run_test(self, lab_name: str, fault_name: str, max_steps: int = 50):
        os.environ["LAB_NAME"] = lab_name
        # 记录准确时刻
        T = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🚀 {T}【测试】环境: [{lab_name}] -> 故障: [{fault_name}]")
        
        try:
            print(f"[System] 🛠️  正在部署网络拓扑 ({lab_name} via {lab_name}.py)...")
            cmd = ["uv", "run", f"{lab_name}.py"]
            cwd = os.path.abspath(os.path.join(current_dir, "net_env"))
            
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[Error] ❌ 拓扑部署失败:\n{result.stderr}")
            
            print(f"[System] ✅ 部署完成！缓冲 4 秒等待路由收敛...")
            time.sleep(4)

            api = KlonetBaseAPI(lab_name)
            raw_topo_dict = api.get_topo_json() 
            netenv_info = simplify_topo(lab_name, raw_topo_dict)
            
            inj_pool = FaultInjector(lab_name)
            category, _ = inj_pool.FAULT_MAP.get(f"inject_{fault_name}")
            cfg = CATE_TABLE.get(category).get(lab_name)

            inj_pool.inject(f"inject_{fault_name}")
            time.sleep(2)
            problem_info = generate_problem_info(fault_name, cfg)

            print('━'*70)
            print("[System] 🧠 启动 Agent 诊断与评估流程...")
            initial_state = {
                "lab_name": lab_name,
                "netenv_info": netenv_info,
                "problem_info": problem_info,
                "expected_fault": fault_name,
                "max_steps": max_steps,
                "actor_model": self.actor_model,
                "judge_model": self.judge_model
            }
            
            app = build_agent_graph()
            final_state = await app.ainvoke(initial_state)
            
            file_name = f"{lab_name}环境{fault_name}故障诊断报告.md"
            file_path = os.path.join(self.results_dir, file_name)
            Time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report = (
            f"\n📊 {Time}【评估报告】\n"
            f"✅ 客观正确性: {final_state['is_correct']}\n"
            f"预期故障: {final_state['expected_fault']} | 诊断结果: {final_state['diagnosis_result']}\n"
            f"⏱️ 耗时: {final_state['execution_time']} 秒\n"
            f"🛠️ 工具调用: {final_state['tool_call_count']} 次\n"
            f"🪙 Token 消耗: {final_state['token_usage']}\n"
            f"🌟 主观逻辑得分: {final_state['subjective_score']} / 10\n"
            f"📝 裁判点评:\n{final_state['subjective_reasoning']}\n")
        
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(report)

            print(f"📝 报告已写入: {file_path}")
            print(report)
            print('━'*70)
                
        except Exception as e:
            print(f"测试用例 {fault_name} 异常: {e}")

        finally:
            print(f"[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
            try:
                api = KlonetBaseAPI(lab_name)
                api.lab.reset_project()
                print("[System] ✅ 拓扑销毁成功。")
            except Exception as reset_e:
                print(f"[System] ❌ 拓扑销毁出错跳过: {reset_e}")
            time.sleep(3)

