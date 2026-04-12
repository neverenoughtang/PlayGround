# agent/test/ultimate_test.py
import os
import sys
import re
import asyncio
import traceback

# --- 路径配置 (适配跨包调用) ---
current_dir = os.path.dirname(os.path.abspath(__file__)) # agent/test
agent_dir = os.path.dirname(current_dir)                 # agent
src_dir = os.path.dirname(agent_dir)                     # src
project_root = os.path.dirname(src_dir)

if agent_dir not in sys.path: sys.path.insert(0, agent_dir)
if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

from mcp_server.klonet_base_api import KlonetBaseAPI
from network_deploy_agent import build_deploy_graph
from fault_inject_agent import build_inject_graph
from diagnose_agent import diagnose_fault
from judge_agent import build_judge_graph

def reset_topology(lab_name: str):
    print(f"\n[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
    try:
        api = KlonetBaseAPI(lab_name)
        api.lab.reset_project()
        print("[System] ✅ 拓扑销毁成功。")
    except Exception as e:
        print(f"[Error] ❌ 拓扑销毁失败: {e}")

async def run_single_test(fault_info: dict, results_dir: str):
    """
    负责执行单一故障的自动化端到端测试，保存 log 日志。
    """
    lab_name = None
    expected_fault = fault_info['expected_fault']
    log_file = os.path.join(results_dir, f"{expected_fault}.log")
    
    # 日志记录器
    log_content = []
    def write_log(msg: str):
        print(msg)
        log_content.append(msg)

    write_log(f"========== 🚀 开始测试: {fault_info['title']} ({expected_fault}) ==========")
    write_log(f"目标场景: {fault_info['scenario']} | 故障现象: {fault_info['problem_info']}")
    
    try:
        # 1. 自动部署
        write_log("\n[1/4] 🔨 开始自动部署拓扑...")
        deploy_graph = build_deploy_graph()
        deploy_state = await deploy_graph.ainvoke({
            "user_query": f"部署{fault_info['scenario']} 场景。",
            "deploy_model": "qwen3.5-27b",
            "lab_name": "", "deploy_status": "", "netenv_info": ""
        })
        lab_name = deploy_state["lab_name"]
        netenv_info = deploy_state["netenv_info"]
        write_log(f"✅ 部署完成。当前拓扑: {lab_name}")

        # 2. 自动注入
        write_log("\n[2/4] 💉 开始自动注入故障...")
        inject_graph = build_inject_graph()
        inject_state = await inject_graph.ainvoke({
            "lab_name": lab_name,
            "netenv_info": netenv_info,
            "fault_query": f"请注入故障: {expected_fault}",
            "actor_model": "qwen3.5-27b",
            "max_steps": 10
        })
        problem_info = fault_info["problem_info"]
        expected_location = inject_state.get("expected_location", "未知")
        write_log(f"✅ 注入完成。故障节点预计为: {expected_location}")

        # 3. 自动诊断
        write_log("\n[3/4] 🩺 开始自动诊断排查...")
        diag_result = await diagnose_fault(
            lab_name=lab_name,
            netenv_info=netenv_info,
            problem_info=problem_info,
            expected_fault=expected_fault,
            expected_location=expected_location,
            backend_model="qwen3.5-27b",
            max_steps=400,
            time_limit=300.0
        )
        write_log(f"✅ 诊断结束。最终结果根因: {diag_result['diagnosis_result']}")
        write_log(f"   定位是否正确: {diag_result['location_correct']}")
        write_log(f"   归因是否正确: {diag_result['attribution_correct']}")
        write_log(f"   排查耗时: {diag_result['execution_time']:.2f} 秒")

        # 4. 自动评测
        write_log("\n[4/4] ⚖️ 开始裁判模型评测...")
        judge_graph = build_judge_graph()
        judge_state = await judge_graph.ainvoke({
            "netenv_info": netenv_info,
            "problem_info": problem_info,
            "expected_fault": expected_fault,
            "expected_location": expected_location,
            "diagnosis_result": diag_result["diagnosis_result"],
            "fault_location": diag_result["fault_location"],
            "location_correct": diag_result["location_correct"],
            "attribution_correct": diag_result["attribution_correct"],
            "tool_call_count": diag_result["tool_call_count"],
            "execution_time": diag_result["execution_time"],
            "token_usage": diag_result["token_usage"],
            "trajectory": "详见系统标准输出",
            "judge_model": "qwen3.5-27b"
        })
        write_log(f"✅ 评测完毕。综合得分: {judge_state.get('综合_score')}")
        write_log(f"主观评价:\n{judge_state.get('subjective_reasoning')}")

    except Exception as e:
        write_log(f"\n❌ 测试过程发生严重异常: {str(e)}")
        write_log(traceback.format_exc())
    finally:
        if lab_name:
            reset_topology(lab_name)

    # 保存日志
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(log_content))
    print(f"\n📁 故障 [{expected_fault}] 的自动化测试日志已归档至: {log_file}")

async def main():
    """
    主控程序：读取 Markdown 文件，正则匹配所有的故障测试用例，并开始跑批测试。
    """
    faults = {
                'title': "第一个故障",
                'scenario': "static_routing",
                'expected_fault': "link_latency",
                'problem_info': "用户反馈通信延迟极高"
            }

   
    # 创建结果存放文件夹
    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    # 依次执行自动化测试
    for i, fault in enumerate(faults):
        print("\n" + "="*80)
        print(f"🌟 当前系统测试进度: {i+1} / {len(faults)}")
        print("="*80)
        await run_single_test(fault, results_dir)

if __name__ == "__main__":
    asyncio.run(main())