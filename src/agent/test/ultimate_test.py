# agent/test/ultimate_test.py
import asyncio
import os
import sys
import traceback
from datetime import datetime

# --- 路径配置 (适配跨包调用) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(agent_dir)

if src_dir not in sys.path: 
    sys.path.insert(0, src_dir)

# 导入所有组件
from mcp_server.klonet_base_api import KlonetBaseAPI
from agent.network_deploy_agent import build_deploy_graph
from agent.fault_inject_agent import build_inject_graph
from agent.diagnose_agent import diagnose_fault
from agent.judge_agent import build_judge_graph

# 导入上面写好的 58 个测试用例
from ultimate_test_cases import TEST_CASES

# ==========================================
# 工具类：TeeLogger (双向日志输出)
# ==========================================
class TeeLogger:
    """
    重定向标准输出，实现“控制台打印”和“文件写入”同步进行。
    使用追加模式 ("a")，不清空历史日志。
    """
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log_file = open(filename, "a", encoding="utf-8")
        
        # 每次运行前写入一个时间戳分割线
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_file.write(f"\n\n{'='*80}\n🚀 测试启动时间: {start_time}\n{'='*80}\n")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush() # 实时刷入文件

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        self.log_file.close()


def reset_topology(lab_name: str):
    """销毁拓扑"""
    print(f"\n[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
    try:
        api = KlonetBaseAPI(lab_name)
        api.lab.reset_project()
        print("[System] ✅ 拓扑销毁成功。")
    except Exception as e:
        print(f"[Error] ❌ 拓扑销毁失败: {e}")

# ==========================================
# 核心函数：执行单一测试流
# ==========================================
async def run_single_test(case: dict, results_dir: str):
    fault_name = case["fault_name"]
    log_path = os.path.join(results_dir, f"{fault_name}.log")

    # 1. 替换标准输出，开始记录日志
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    tee = TeeLogger(log_path)
    sys.stdout = tee
    sys.stderr = tee

    lab_name = None
    try:
        print("=" * 80)
        print(f"⚡ 开始测试: [{fault_name}]")
        print(f"📋 部署需求: {case['deploy_query']}")
        print(f"💉 注入需求: {case['fault_query']}")
        print("=" * 80)

        # 【阶段一】：部署拓扑
        print("\n[1/4] 🔨 开始自动部署拓扑...")
        deploy_graph = build_deploy_graph()
        deploy_state = await deploy_graph.ainvoke({
            "user_query": case["deploy_query"],
            "deploy_model": "qwen3.5-27b",
            "lab_name": "", "deploy_status": "", "netenv_info": ""
        })
        lab_name = deploy_state["lab_name"]
        netenv_info = deploy_state["netenv_info"]

        # 【阶段二】：注入故障
        print("\n[2/4] 💉 开始自动注入故障...")
        inject_graph = build_inject_graph()
        inject_state = await inject_graph.ainvoke({
            "lab_name": lab_name,
            "netenv_info": netenv_info,
            "fault_query": case["fault_query"],
            "actor_model": "qwen3.5-27b",
            "max_steps": 100
        })
        problem_info = inject_state["problem_info"]
        expected_fault = inject_state["expected_fault"]
        expected_location = inject_state["expected_location"]

        # 【阶段三】：智能诊断排查
        print("\n[3/4] 🩺 开始自动诊断排查...")
        diag_result = await diagnose_fault(
            lab_name=lab_name,
            netenv_info=netenv_info,
            problem_info=problem_info,
            expected_fault=expected_fault,
            expected_location=expected_location,
            backend_model="qwen3.5-27b",
            max_steps=200,     # 给足 20 步探索机会
            time_limit=1800.0  # 限制最长 10 分钟
        )

        # 【阶段四】：裁判模型评测
        print("\n[4/4] ⚖️ 开始裁判模型评测...")
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
            "trajectory": diag_result["full_trajectory"],
            "judge_model": "qwen3.5-27b"
        })

        print("\n" + "=" * 60)
        print(f"🏆 [Judge] 最终综合评分: {judge_state.get('综合_score', 0)} / 100")
        print(f"📝 [Judge] 详细评价理由:\n{judge_state.get('subjective_reasoning', '无')}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试过程发生严重异常: {e}")
        traceback.print_exc()
    finally:
        # 无论成功失败，销毁底层拓扑
        if lab_name:
            reset_topology(lab_name)
            
        # 恢复标准输出，关闭文件流
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        tee.close()
        print(f"✅ 用例 [{fault_name}] 测试结束，日志追加至: {log_path}")

# ==========================================
# 主流程：串行循环全部用例
# ==========================================
async def main():
    results_dir = os.path.join(current_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    print("=" * 80)
    print(f"🌟 开始批量自动化测试，共加载 {len(TEST_CASES)} 个故障用例。")
    print("=" * 80)
    
    for i, case in enumerate(TEST_CASES):
        print(f"\n⏳ 进度: [{i+1}/{len(TEST_CASES)}] - 准备执行用例: {case['fault_name']}")
        await run_single_test(case, results_dir)

if __name__ == "__main__":
    # 如果遇到 Windows/某些 Linux 环境的 asyncio 报错，可取消注释下面这行
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())