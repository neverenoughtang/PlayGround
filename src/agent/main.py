# agent/main.py
import asyncio
import os
import sys

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
if src_dir not in sys.path: 
    sys.path.insert(0, src_dir)

# 导入底层接口
from mcp_server.klonet_base_api import KlonetBaseAPI

# 导入各个板块的 Agent 执行图
from network_deploy_agent import build_deploy_graph
from fault_inject_agent import build_inject_graph
from diagnose_agent import diagnose_fault
from judge_agent import build_judge_graph

def reset_topology(lab_name: str):
    """
    公共方法：销毁指定的网络拓扑
    """
    print(f"\n[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
    try:
        api = KlonetBaseAPI(lab_name)
        api.lab.reset_project()
        print("[System] ✅ 拓扑销毁成功。")
    except Exception as e:
        print(f"[Error] ❌ 拓扑销毁失败: {e}")

async def main():
    print("=" * 60)
    print("🚀 欢迎使用网络故障诊断智能体系统")
    print("=" * 60)

    lab_name = None
    try:
        # ==========================================
        # 1. 网络场景部署 -> Human_in_Loop
        # ==========================================
        while True:
            deploy_query = input("\n[HIL - 部署阶段] 请输入要部署的网络场景 (例如：我需要一个静态路由网络): ")
            
            # 初始化部署图并运行
            deploy_graph = build_deploy_graph()
            deploy_state = await deploy_graph.ainvoke({
                "user_query": deploy_query, 
                "deploy_model": "qwen3.5-27b", # 默认使用 qwen 决策
                "lab_name": "", 
                "deploy_status": "", 
                "netenv_info": ""
            })
            
            lab_name = deploy_state["lab_name"]
            netenv_info = deploy_state["netenv_info"]
            
            # HIL: 抉择下一步
            choice = input("\n[HIL] 👉 请选择下一步:\n"
                           "  - 输入 'r' 销毁当前拓扑并重新部署\n"
                           "  - 直接输入【故障注入需求】进入下一步注入阶段: ")
            
            if choice.strip().lower() == 'r':
                reset_topology(lab_name)
                continue
            else:
                fault_query = choice.strip()
                break

        # ==========================================
        # 2. 网络故障注入 -> Human_in_Loop
        # ==========================================
        while True:
            # 初始化注入图并运行
            inject_graph = build_inject_graph()
            inject_state = await inject_graph.ainvoke({
                "lab_name": lab_name,
                "netenv_info": netenv_info,
                "fault_query": fault_query,
                "actor_model": "qwen3.5-27b",
                "max_steps": 15
            })
            
            problem_info = inject_state["problem_info"]
            expected_fault = inject_state["expected_fault"]
            expected_location = inject_state["expected_location"]

            # HIL: 抉择下一步
            choice = input("\n[HIL] 👉 请选择下一步:\n"
                           "  - 输入 'r' 重新进行故障注入\n"
                           "  - 输入 'd' 进入下一步开始诊断: ")
            
            if choice.strip().lower() == 'r':
                fault_query = input("\n[HIL] 请输入新的【故障注入需求】: ")
                continue
            elif choice.strip().lower() == 'd':
                break

        # ==========================================
        # 3. 故障诊断 -> Human_in_Loop
        # ==========================================
        diag_result = None
        while True:
            # 提示用户选择大模型及执行次数
            diag_model = input("\n[HIL - 诊断阶段] 请输入用于诊断的 LLM 模型名 (回车默认 qwen3.5-27b): ") or "qwen3.5-27b"
            max_steps_input = input("[HIL - 诊断阶段] 请输入最大执行次数 (回车默认 100): ") or "100"
            
            diag_result = await diagnose_fault(
                lab_name=lab_name,
                netenv_info=netenv_info,
                problem_info=problem_info,
                expected_fault=expected_fault,
                expected_location=expected_location,
                backend_model=diag_model,
                max_steps=int(max_steps_input),
                time_limit=1200.0
            )

            # HIL: 抉择下一步
            choice = input("\n[HIL] 👉 请选择下一步:\n"
                           "  - 输入 'r' 重新进行诊断\n"
                           "  - 输入 'e' 进入下一步开始评测: ")
            
            if choice.strip().lower() == 'r':
                continue
            elif choice.strip().lower() == 'e':
                break

        # ==========================================
        # 4. 诊断效果评测 -> 结束
        # ==========================================
        judge_model = input("\n[HIL - 评测阶段] 请选择测评 LLM 模型 (回车默认 qwen3.5-27b): ") or "qwen3.5-27b"
        
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
            "trajectory": "见系统运行日志", 
            "judge_model": judge_model
        })

        print("\n" + "=" * 60)
        print(f"🏆 [Judge] 最终综合评分: {judge_state['综合_score']} / 100")
        print(f"📝 [Judge] 详细评价理由:\n{judge_state['subjective_reasoning']}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n⚠️ [System] 检测到用户强制中断 (Ctrl+C)。")
    except Exception as e:
        print(f"\n❌ [System] 运行期间发生未捕获异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 无论发生什么，保证实验拓扑环境被正确销毁
        if lab_name:
            reset_topology(lab_name)

if __name__ == "__main__":
    asyncio.run(main())