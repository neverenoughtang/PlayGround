import asyncio
import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
if src_dir not in sys.path: 
    sys.path.insert(0, src_dir)

# 导入底层接口
from mcp_server.klonet_base_api import KlonetBaseAPI

# 导入各个板块的图
from network_deploy_agent import build_deploy_graph
from fault_inject_agent import build_inject_graph
from diagnose_agent.graph import diagnose_fault
from judge_agent import build_judge_graph


def reset_topology(lab_name: str):
    print(f"\n[System] 🧹 正在销毁网络拓扑 ({lab_name})...")
    try:
        api = KlonetBaseAPI(lab_name)
        api.lab.reset_project()
        # 【核心修复】：底层网络资源（Docker/OVS/Redis）的销毁是异步且耗时的！
        # 必须强行设置一个缓冲期，绝不能立刻重试，否则会撞上还没释放的旧缓存。
        print("[System] ⏳ 正在等待 Klonet 底层容器与 Redis 缓存彻底释放 (约 6 秒)...")
        time.sleep(6)        
        print("[System] ✅ 拓扑销毁成功。")
    except Exception as e:
        print(f"[Error] ❌ 拓扑销毁失败: {e}")

async def main():
    print("=" * 60)
    print("🚀 欢迎使用 Argus 网络故障仿真与诊断智能体系统")
    print("=" * 60)

    lab_name = None
    total_time = 0
    try:
        # ==========================================
        # 1. 网络场景部署 
        # ==========================================
        while True:
            deploy_query = input("\n[HIL - 部署阶段] 请输入要部署的网络场景 (例如：我需要一个静态路由网络): ")
            
            # 初始化部署图并运行
            deploy_graph = build_deploy_graph()
            deploy_state = await deploy_graph.ainvoke({
                "user_query": deploy_query, 
                "deploy_model": "qwen3.6-medium", # 默认使用 qwen 决策
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
        # 2. 故障注入阶段 -> HIL
        # ==========================================
        while True:
            inject_graph = build_inject_graph()
            inject_state = await inject_graph.ainvoke({
                "lab_name": lab_name,
                "netenv_info": netenv_info,
                "fault_query": fault_query,
                "actor_model": "qwen3.6-medium", # 注入流程相对轻量
                "max_steps": 150,
                "inject_result": "",
                "problem_info": "",
                "expected_faults": {}
            })
            
            if inject_state["inject_result"] == "fatal":
                print("\n❌ [System] 注入智能体遭遇致命错误退出，停止后续流程。")
                return

            problem_info = inject_state["problem_info"]
            expected_faults = inject_state["expected_faults"]
            
            print(f"\n✅ [System] 故障注入完成！")
            print(f"预期答案: {expected_faults}")
            print(f"生成的学生投诉: {problem_info}")
            
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
        # 3. 故障诊断阶段 (Argus 主从阵列)
        # ==========================================
        while True:
            steps_input = input("[HIL - 诊断阶段] 请输入最大执行次数 (默认 200): ")    
            max_steps_input = int(steps_input) if steps_input else 200
            start_time = time.perf_counter()

            diag_result = await diagnose_fault(
                lab_name=lab_name,
                netenv_info=netenv_info,
                problem_info=problem_info,
                expected_faults=expected_faults,
                max_steps=max_steps_input,
                time_limit=1800.0
            )

            total_time = time.perf_counter() - start_time
            # HIL: 抉择下一步
            choice = input("\n[HIL] 👉 请选择下一步:\n"
                           "  - 输入 'r' 重新进行诊断\n"
                           "  - 输入 'e' 进入下一步开始评测: ")
            
            if choice.strip().lower() == 'r':
                continue
            elif choice.strip().lower() == 'e':
                break

        # ==========================================
        # 4. 评测阶段 (Judge)
        # ==========================================
        judge_graph = build_judge_graph()
        judge_state = await judge_graph.ainvoke({
            "netenv_info": netenv_info,
            "problem_info": problem_info,
            "final_faults": diag_result.get("final_faults", {}),
            "precision": diag_result.get("precision", 0.0),
            "recall": diag_result.get("recall", 0.0),
            "tool_call_count": diag_result.get("global_tool_calls", 0),
            "execution_time": total_time or diag_result.get("execution_time"),
            "token_usage": diag_result.get("global_token_usage", {}),
            "trajectory": diag_result.get("trajectory", "无轨迹记录"), 
            "judge_model": "qwen3.6-big" # 裁判使用最强推理模型
        })

    except KeyboardInterrupt:
        print("\n⚠️ [System] 检测到用户强制中断 (Ctrl+C)。")
    except Exception as e:
        print(f"\n❌ [System] 系统严重异常: {e}")
    finally:
        if lab_name:
            reset_topology(lab_name)

if __name__ == "__main__":
    asyncio.run(main())