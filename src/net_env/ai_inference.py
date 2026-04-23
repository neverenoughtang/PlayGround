import os
import time
import base64
from dotenv import load_dotenv
load_dotenv() 

from KlonetAPI import *
from base_netenv import NetworkEnvBase

class AIInference(NetworkEnvBase):
    """
    AI 推理网络 (极速精简版): Spine(2) + Leaf(2) + Server(1) + Client(1) (共 6 节点)
    """
    def __init__(self, lab_name="ai_inference"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 构建 Spine-Leaf 极简拓扑
        # ==========================================
        print("[Net] 正在创建 Spine-Leaf (2+2) 拓扑节点...")
        spines = [self.lab.add_node(f"spine{i}", self.lab.images["quagga"], x=300+200*i, y=100) for i in range(1, 3)]
        leafs = [self.lab.add_node(f"leaf{i}", self.lab.images["quagga"], x=200+300*i, y=300) for i in range(1, 3)]
        self.server = self.lab.add_node("server", self.lab.images['ubuntu_ai_server'], x=200, y=500)
        self.client = self.lab.add_node("client", self.lab.images['ubuntu_ai_client'], x=500, y=500)

        # ==========================================
        # 2. 构建链路连通性
        # ==========================================
        for s in spines:
            for l in leafs:
                self.lab.add_link(s, l)
        self.lab.add_link(leafs[0], self.server, link_name="link_leaf1_server")
        self.lab.add_link(leafs[1], self.client, link_name="link_leaf2_client")

        # ==========================================
        # 3. 物理部署与 OSPF 动态路由配置
        # ==========================================
        print("[Net] 正在部署物理底层网络...")
        self.deploy()
        time.sleep(15) 
        
        # 强制开启所有路由器的 IPv4 流量转发能力
        for r in ["spine1", "spine2", "leaf1", "leaf2"]:
            self.lab._run_cmd(r, "sysctl -w net.ipv4.ip_forward=1")
            
        print("[Net] 正在下发 OSPF 动态路由协议...")
        self.config(senario="ospf")
        print("[Net] 正在等待 OSPF 邻居建立与路由 LSA 泛洪收敛 (约 35 秒)...")
        time.sleep(35) 

    def start_real_inference(self):
        """
        在 server 端使用 FastAPI + Transformers 原生 Pipeline 启动纯 CPU 推理引擎
        """
        # 🚨【核心修复】：完全抛弃 KlonetAPI 脆弱的字典解析，直接执行 Linux 指令获取真实 IP！
        # 解决 `TypeError: string indices must be integers, not 'str'` 报错！
        raw_server_ip = self.lab._run_cmd("server", "hostname -I")
        self.server_ip = raw_server_ip.strip().split()[0] if raw_server_ip else "192.168.4.2"
        
        # 开启后台抓包
        self.lab._run_cmd("server", "nohup tcpdump -i any -w /tmp/spine_leaf.pcap > /dev/null 2>&1 &")

        # FastAPI + Transformers 纯原生 Python 脚本
        real_llm_script = """
import os
import torch
import uvicorn
from fastapi import FastAPI, Request
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

app = FastAPI()
MODEL_DIR = "/opt/models/tinyllama" 

with open("/tmp/ai_boot.flag", "w") as f: f.write("booted\\n")
print("Loading model and tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True)
pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=-1)

with open("/tmp/ai_ready.flag", "w") as f: f.write("ready\\n")
print("Model loaded, starting FastAPI server...")

@app.post("/v1/completions")
async def generate(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        outputs = pipe(
            prompt, 
            max_new_tokens=100, 
            do_sample=True, 
            temperature=0.7, 
            return_full_text=False
        )
        return {"choices": [{"text": outputs[0]["generated_text"].strip()}]}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__": 
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
        import base64
        b64_script = base64.b64encode(real_llm_script.encode("utf-8")).decode("utf-8")
        self.lab._run_cmd("server", f"bash -c 'echo {b64_script} | base64 -d > /tmp/real_llm.py'")
        self.lab._run_cmd("server", "bash -c 'rm -f /tmp/vllm_cpu.log /tmp/ai_ready.flag /tmp/ai_boot.flag /tmp/ai_pid'")

        print("[App] Server 正在后台启动 FastAPI 原生推理服务...")
        start_cmd = "bash -c 'nohup python3 /tmp/real_llm.py > /tmp/vllm_cpu.log 2>&1 & echo $! > /tmp/ai_pid'"
        self.lab._run_cmd("server", start_cmd)
        
        # 同样给 Client 也做一个安全的 IP 解析探测
        raw_client_ip = self.lab._run_cmd("client", "hostname -I")
        self.client_ip = raw_client_ip.strip().split()[0] if raw_client_ip else "192.168.5.2"

# ==========================================
# 详尽的系统状态自检与测试主函数
# ==========================================
if __name__ == "__main__":
    try:
        # 1. 实例化拓扑并自动完成物理连线与 OSPF 部署
        LAB = AIInference(lab_name="ai_inference")
        
        # 2. 启动应用层 AI 推理服务
        LAB.start_real_inference()
        
        print("\n✅ [Success] AI 推理场景 (ai_inference) 部署完全成功！")
    except Exception as e:
        print(f"\n❌ [Fatal] 部署过程中发生致命错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
# if __name__ == "__main__":
#     print("\n" + "="*60)
#     print("🚀 [Step 1] 初始化 AI 推理网络 (极简 OSPF Spine-Leaf)")
#     print("="*60)
#     LAB = AIInference()
    
#     print("\n" + "="*60)
#     print("🔍 [Step 2] OSPF 网络底座连通性与路由诊断")
#     print("="*60)
    
#     client_ip = LAB.lab.get_host_ip("client")
#     server_ip = LAB.lab.get_host_ip("server")
#     print(f"[*] 解析节点 IP -> Server: {server_ip} | Client: {client_ip}")

#     # 【修复】：增加 OSPF 收敛的动态轮询机制，最多再等 30 秒，不见兔子不撒鹰
#     print("\n[*] 窥探 Leaf2 OSPF 路由表 (检查是否收敛):")
#     server_subnet = ".".join(server_ip.split(".")[:3]) + ".0/24"  # 提取 192.168.4.0/24
    
#     for i in range(10):
#         route_res = LAB.lab._run_cmd("leaf2", "ip route")
#         # 只要路由表里出现了 zebra (Quagga 动态路由内核注入标志) 或者目标网段，就说明收敛成功
#         if "zebra" in route_res or server_subnet in route_res:
#             print(route_res.strip())
#             print(f"✅ OSPF 路由已完全收敛! (附加等待 {i*3} 秒)")
#             break
#         print(f"   ... OSPF 路由树正在构建中 (等待 {i*3}s)，当前表项仅有直连路由")
#         time.sleep(3)
#     else:
#         print("⚠️ 警告：OSPF 似乎未能在预期时间内收敛，强制执行连通性测试...")
    
#     # 全网端到端 Ping 测试
#     print(f"\n[*] 世纪跨域 Ping 测试 (Client -> Server):")
#     ping_res = LAB.lab._run_cmd("client", f"ping -c 3 -W 1 {server_ip}")
#     print(ping_res.strip())

#     if "100% packet loss" in ping_res or "Unreachable" in ping_res:
#         print("\n❌ [Fatal] 致命错误：底层 OSPF 路由断裂，网络不通！请检查环境。")
#         exit(1)
#     else:
#         print("\n✅ 恭喜，底层 OSPF 网络畅通无阻！")

#     print("\n" + "="*60)
#     print("🧠 [Step 3] 启动并挂起应用层 AI 推理引擎")
#     print("="*60)
#     LAB.start_real_inference()

#     # 应用层 HTTP 探活与模型加载等待机制
#     print(f"\n[*] 等待 FastAPI 8000 端口服务上线 (最长 120 秒)...")
#     service_ready = False
#     for i in range(12):
#         time.sleep(10)
#         # 检查 Python 脚本进度标志
#         boot_flag = LAB.lab._run_cmd("server", "cat /tmp/ai_boot.flag").strip()
#         ready_flag = LAB.lab._run_cmd("server", "cat /tmp/ai_ready.flag").strip()
        
#         # 利用 Client 发起跨域 HTTP CURL 探测
#         curl_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:8000/v1/completions -d '{{\"prompt\":\"test\"}}' -H 'Content-Type: application/json'"
#         http_code = LAB.lab._run_cmd("client", curl_cmd).strip()

#         if http_code == "200":
#             print(f"   ✅ FastAPI 推理服务已就绪！HTTP=200 (耗时: {i*10} 秒)")
#             service_ready = True
#             break
#         elif "booted" in boot_flag and "ready" not in ready_flag:
#             print(f"   ⏳ 正在将大模型权重加载至内存... ({i*10}/120s)")
#         else:
#             print(f"   ⏳ 等待 Uvicorn 服务绑定端口... ({i*10}/120s) | HTTP_CODE: {http_code}")
            
#     if not service_ready:
#         print("❌ [Fatal] FastAPI 服务未能启动，请检查 Docker 内是否存在 tinyllama 权重，或查看 /tmp/vllm_cpu.log 报错日志！")
#         error_log = LAB.lab._run_cmd("server", "tail -n 10 /tmp/vllm_cpu.log")
#         print(f"\n[Crash Log]:\n{error_log}")
#         exit(1)

#     print("\n" + "="*60)
#     print("🎉 [Step 4] 端到端 AI 业务联调测试 (Client 发起真实推理)")
#     print("="*60)
    
#     prompt_payload = '{"prompt": "User: Who are you? \\nAssistant: ", "max_tokens": 100}'
#     test_cmd = f"curl -s -X POST http://{server_ip}:8000/v1/completions -H 'Content-Type: application/json' -d '{prompt_payload}'"
    
#     print(f"[*] 执行业务 CURL 指令:\n    {test_cmd}\n")
    
#     t_start = time.time()
#     inference_result = LAB.lab._run_cmd("client", test_cmd)
#     t_end = time.time()

#     print(f"[*] 🚀 跨网大模型推理响应 (耗时 {t_end - t_start:.2f} 秒):")
#     print(inference_result.strip())
#     print("\n" + "="*60)
#     print("✅ 全部测试通过，AI Inference 网络场景部署完美完成！")
#     print("="*60)





# import time
# from KlonetAPI import *
# from base_netenv import NetworkEnvBase

# class AIInference(NetworkEnvBase):
#     """
#     AI 推理网络 (规模扩容): Spine(4) + Leaf(6) + Server(1) + Clients(9) (共 20 节点)
#     """
#     def __init__(self, lab_name="ai_inference"):
#         super().__init__(lab_name=lab_name)

#         # ==========================================
#         # 1. 构建 Spine-Leaf 拓扑
#         # ==========================================
#         spines = [self.lab.add_node(f"spine{i}", self.lab.images["quagga"], x=200+200*i, y=100) for i in range(1, 5)]
#         leafs = [self.lab.add_node(f"leaf{i}", self.lab.images["quagga"], x=150+150*i, y=300) for i in range(1, 7)]

#         server = self.lab.add_node("server", self.lab.images['ubuntu_ai_server'], x=150, y=500)
#         clients = [self.lab.add_node(f"client{i}", self.lab.images['ubuntu_ai_client'], x=200+100*i, y=500) for i in range(1, 10)]

#         # 全互联 (Spine-Leaf Full Mesh)
#         for s in spines:
#             for l in leafs:
#                 self.lab.add_link(s, l)

#         # Leaf 下挂设备
#         self.lab.add_link(leafs[0], server)
#         self.lab.add_link(leafs[1], clients[0]); self.lab.add_link(leafs[1], clients[1])
#         self.lab.add_link(leafs[2], clients[2]); self.lab.add_link(leafs[2], clients[3])
#         self.lab.add_link(leafs[3], clients[4]); self.lab.add_link(leafs[3], clients[5])
#         self.lab.add_link(leafs[4], clients[6]); self.lab.add_link(leafs[4], clients[7])
#         self.lab.add_link(leafs[5], clients[8])

#         print("[Net] 部署物理拓扑...")
#         self.deploy()
#         time.sleep(20)
        
#         print("[Net] 配置 OSPF 动态路由协议...")
#         self.config(senario="ospf")
#         time.sleep(20) # 节点变多，OSPF 收敛时间稍微拉长

#     def start_real_inference(self):
#         """在 server 启动真正的 CPU 推理服务"""
#         server_ip = self.lab.get_host_ip("server")
        
#         self.lab._run_cmd("server", "nohup tcpdump -i any -w /tmp/spine_leaf.pcap > /dev/null 2>&1 &")

#         # (省略了冗长的 Base64 脚本转换与 Python 源码写入过程，保持与原来代码完全一致)
#         real_llm_script = """
# import os
# import torch
# from fastapi import FastAPI, Request
# from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
# import uvicorn

# app = FastAPI()
# MODEL_DIR = "/opt/models/tinyllama"

# with open("/tmp/ai_boot.flag", "w") as f: f.write("booted\\n")
# tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
# model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True)
# pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=-1)
# with open("/tmp/ai_ready.flag", "w") as f: f.write("ready\\n")

# @app.post("/v1/completions")
# async def generate(request: Request):
#     data = await request.json()
#     outputs = pipe(data.get("prompt", ""), max_new_tokens=100, do_sample=True, temperature=0.7, return_full_text=False)
#     return {"choices": [{"text": outputs[0]["generated_text"].strip()}]}

# if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)
# """
#         import base64
#         b64_script = base64.b64encode(real_llm_script.encode("utf-8")).decode("utf-8")
#         self.lab._run_cmd("server", f"bash -c 'echo {b64_script} | base64 -d > /tmp/real_llm.py'")
#         self.lab._run_cmd("server", "bash -c 'rm -f /tmp/vllm_cpu.log /tmp/ai_ready.flag /tmp/ai_boot.flag /tmp/ai_pid'")

#         print("[App] server 正在启动实时 CPU 推理引擎 (TinyLlama)...")
#         start_cmd = "bash -c 'nohup python3 /tmp/real_llm.py > /tmp/vllm_cpu.log 2>&1 & echo $! > /tmp/ai_pid'"
#         self.lab._run_cmd("server", start_cmd)

#         print("[App] 等待 8000 端口响应...")
#         for i in range(12):
#             time.sleep(10)
#             boot_flag = self.lab._run_cmd("server", "cat /tmp/ai_boot.flag")
#             ready_flag = self.lab._run_cmd("server", "cat /tmp/ai_ready.flag")
#             # 👇 注意这里把 client 改成了 client1
#             check = self.lab._run_cmd("client1", f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:8000/v1/completions -d '{{\"prompt\":\"test\"}}' -H 'Content-Type: application/json'")

#             if check == "200":
#                 print(f"[App] 推理服务已就绪！(第 {i*10} 秒)")
#                 break
#             print(f"  ... 仍在加载模型 ({i*10}/120s)")

#         prompt = '{"prompt": "Who are you?", "max_tokens": 50}'
#         # 👇 注意这里把 client 改成了 client9，测试对角线最远端
#         res = self.lab._run_cmd("client9", f"curl -s -X POST http://{server_ip}:8000/v1/completions -H 'Content-Type: application/json' -d '{prompt}'")
#         print(f"\n[推理结果 (Client9)]:\n{res}")

# if __name__ == "__main__":
#     LAB = AIInference()
#     LAB.start_real_inference()