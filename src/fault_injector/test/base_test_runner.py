import os
import sys
import time
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
injector_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(injector_dir, ".."))
for path in [injector_dir, project_root]:
    if path not in sys.path:
        sys.path.append(path)


from fault_inject_pool import FaultInjector
from service.klonet.base_api import KlonetBaseAPI

def run_scenario_tests(topo_key: str, test_suite: list, INPUT: dict):
    cfg = INPUT.get(topo_key)
    if not cfg:
        print(f"[Error] 未找到 {topo_key} 的配置参数。")
        return

    print(f"\n{'#'*60}")
    print(f"🚀 开始执行场景自动化测试: {topo_key} ({len(test_suite)} 个故障)")
    print(f"{'#'*60}")

    for test_func in test_suite:
        print(f"\n{'-'*60}")
        print(f"[System] 🛠️  正在部署网络拓扑 ({topo_key} via {topo_key}.py)...")
        cmd = ["uv", "run", f"{topo_key}.py"]
        cwd = "/home/lzl/tmx/PlayGround/src/playground/net_env"
        
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[Error] ❌ 拓扑部署失败:\n{result.stderr}")
            continue
        
        print(f"[System] ✅ 部署完成！缓冲 8 秒等待路由收敛...")
        time.sleep(8)
        
        try:
            injector = FaultInjector(topo_key)
            test_func(injector, cfg)
        except Exception as e:
            print(f"\n[Fatal Error] 测试 {test_func.__name__} 时发生异常: {e}")
            
        finally:
            print(f"[System] 🧹 正在销毁网络拓扑 ({topo_key})...")
            try:
                api = KlonetBaseAPI(topo_key)
                api.lab.reset_project()
                print("[System] ✅ 拓扑销毁成功。")
            except:
                pass
            time.sleep(3)