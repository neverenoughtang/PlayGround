# src/agent/test/inject_test.py
import asyncio
import sys
import os
import time
import subprocess
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
playground_dir = os.path.abspath(os.path.join(current_dir, "../../../src/playground"))
if playground_dir not in sys.path: sys.path.insert(0, playground_dir)
if project_root not in sys.path: sys.path.append(project_root)

from mcp_server.klonet_base_api import KlonetBaseAPI 
from src.agent.fault_inject_agent import FaultInjectAgent
from src.agent.test.inject_test_cases import COMPOSITE_TEST_CASES

# ==========================================
# 辅助函数: 精简拓扑信息
# ==========================================
def simplify_topo(lab_name: str, raw_topo: dict) -> str:
    """
    接收全量的拓扑 JSON 字典，过滤掉所有非网络特性的冗余参数，
    仅保留节点(名称/类型/接口/IP/网关)和链路(源/目的及对应IP)。
    """
    simplified = []
    simplified.append(f"{lab_name} 的拓扑信息:")
    
    # 1. 提炼节点信息
    simplified.append("[节点列表]")
    categories = ['controllers', 'hosts', 'routers', 'switches', 'dpdks']
    for category in categories:
        if category not in raw_topo or not raw_topo[category]:
            continue
            
        for node_name, node_info in raw_topo[category].items():
            # 基础网络属性
            node_type = node_info.get('type', category)
            
            # 👇 【新增修复】：智能推断节点真实类型 (覆盖分类不准的情况)
            image_name = node_info.get('image_name', '').lower()
            subtype = node_info.get('subtype', '').lower()
            
            if 'ryu' in image_name or 'ryu' in subtype:
                node_type = 'ryu'
            elif 'bmv2' in image_name or 'bmv2' in subtype or 'p4' in image_name:
                node_type = 'bmv2'
            # 👆 =======================================================
            
            gateway = node_info.get('gateway', '')
            interfaces = node_info.get('interfaces', [])
            
            # 格式化接口
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')

                # 修复：安全解析子网掩码，防止空字符串或非法格式导致 int() 报错
                netmask = iface.get('netmask', '') 
                mask = ""
                if netmask and '.' in netmask:
                    try:
                        mask_len = sum(bin(int(x)).count('1') for x in netmask.split('.'))
                        mask = f"/{mask_len}"
                    except ValueError:
                        mask = "" # 如果解析失败，就不带掩码后缀

                # 修正接口名称：如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname

                # 加上 IP
                if ip:
                    iface_strs.append(f"{actual_iname}({ip}{mask})")
                else:
                    iface_strs.append(f"{actual_iname}")
            
            # 拼接单节点信息
            # 这里的 [node_type] 就会根据上面的智能推断显示出 [ryu] 或 [bmv2]
            info_str = f"- {node_name} [{node_type}]"
            if iface_strs:
                info_str += f" | 接口: {', '.join(iface_strs)}"
            if gateway:
                info_str += f" | 默认网关: {gateway}"
                
            simplified.append(info_str)
            
    # 2. 提炼链路信息 (原代码保持不变)
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
# 核心测试流程
# ==========================================
def run_composite_injection_test(case_idx: int, total_cases: int, test_case: dict):
    """
    完整的创建网络 -> 注入复合故障 -> 验证结果 -> 销毁网络 流程
    """
    lab_name = test_case["lab_name"]
    fault_query = test_case["fault_query"]
    level = test_case["level"]
    expected_faults = test_case["expected_faults_contained"]
    
    os.environ["LAB_NAME"] = lab_name

    print(f"\n" + "🌟"*35)
    print(f"▶️  [执行用例 {case_idx}/{total_cases}] - 复杂度: {level}")
    print(f"📍 测试场景: [{lab_name}]")
    print(f"🗣️ 用户诉求: {fault_query}")
    print(f"🎯 理论包含故障: {expected_faults}")
    print("🌟"*35)
    
    try:
        # 1. 部署底层网络拓扑
        print(f"\n[System] 🛠️ 正在初始化底层网络拓扑容器 ({lab_name}.py)...")
        cmd = ["uv", "run", f"{lab_name}.py"]
        cwd = os.path.abspath(os.path.join(current_dir, "../../../src/net_env"))
        
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Error] ❌ 拓扑部署失败:\n{result.stderr}")
            return
        
        print(f"[System] ✅ 部署完成！缓冲 5 秒等待路由及服务收敛...")
        time.sleep(5)

        # 2. 获取实时拓扑参数
        api = KlonetBaseAPI(lab_name)
        raw_topo_dict = api.get_topo_json() 
        netenv_info = simplify_topo(lab_name, raw_topo_dict)
        
        # 3. 启动大模型注入智能体 (Agentic RAG)
        print(f"\n[System] 🤖 移交控制权给 FaultInjectAgent (开始自主拆解与检索注入)...")
        agent = FaultInjectAgent(
            lab_name=lab_name,
            max_steps=150, # 复合故障操作步骤较多，放宽递归上限
            netenv_info=netenv_info, 
            fault_query=fault_query,
            backend_model="qwen3.5-medium" 
        )
        
        agent_result = asyncio.run(agent.inject_check_fault())
        
        # 4. 评估并打印智能体的复合报告
        print(f"\n📊 [注入智能体复合成果汇报]")
        print(f"✅ 执行状态: {agent_result.get('inject_result', 'N/A')}")
        print(f"🗣️ Agent自动合成的用户投诉:\n  \"{agent_result.get('problem_info', 'N/A')}\"")
        
        # 美化打印 JSON 结果
        submitted_dict = agent_result.get('expected_faults', {})
        print(f"📦 Agent提交的复合故障字典:")
        print(json.dumps(submitted_dict, indent=4, ensure_ascii=False))
        
        # 简单比对一下期待的 key 是否都在提交的字典里
        missed_keys = [k for k in expected_faults if k not in submitted_dict.keys()]
        if missed_keys:
            print(f"⚠️ [评测警告] 似乎漏掉了以下故障类型的注入或记录: {missed_keys}")
        else:
            print(f"🏆 [评测通过] Agent 成功识别并拆解了所有包含的复合故障类型！")

    except Exception as e:
        print(f"❌ 测试运行时发生致命异常: {e}")

    finally:
        # 5. 安全销毁拓扑 (防止脏数据污染下一用例)
        print(f"\n[System] 🧹 测试结束，正在强制销毁网络沙箱 ({lab_name})...")
        try:
            api = KlonetBaseAPI(lab_name)
            api.lab.reset_project()
            print("[System] ✅ 拓扑资源已回收释放。")
        except:
            pass
        time.sleep(4)

# ==========================================
# 启动器
# ==========================================
if __name__ == "__main__":
    total_cases = len(COMPOSITE_TEST_CASES)
    print(f"\n{'='*70}")
    print(f"🧪 [复合注入自动化测试阵列启动]")
    print(f"总计加载测试用例: {total_cases} 条")
    print(f"{'='*70}\n")
    
    # 支持命令行参数指定跑哪一条，例如 `python inject_test.py 15`
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        specific_idx = int(sys.argv[1])
        if 1 <= specific_idx <= total_cases:
            run_composite_injection_test(specific_idx, total_cases, COMPOSITE_TEST_CASES[specific_idx-1])
        else:
            print(f"❌ 索引越界，请输入 1-{total_cases} 之间的数字")
    else:
        # 遍历全量测试
        for idx, test_case in enumerate(COMPOSITE_TEST_CASES, 1):
            run_composite_injection_test(idx, total_cases, test_case)
            
    print(f"\n🎉 [所有复合测试执行完毕]")