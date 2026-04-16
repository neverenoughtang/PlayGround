import time
from KlonetAPI import *
from base_netenv import NetworkEnvBase

class AIInference(NetworkEnvBase):
    """
    AI 推理网络 (规模扩容): Spine(4) + Leaf(6) + Server(1) + Clients(9) (共 20 节点)
    """
    def __init__(self, lab_name="ai_inference"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 构建 Spine-Leaf 拓扑
        # ==========================================
        spines = [self.lab.add_node(f"spine{i}", self.lab.images["quagga"], x=200+200*i, y=100) for i in range(1, 5)]
        leafs = [self.lab.add_node(f"leaf{i}", self.lab.images["quagga"], x=150+150*i, y=300) for i in range(1, 7)]

        server = self.lab.add_node("server", self.lab.images['ubuntu_ai_server'], x=150, y=500)
        clients = [self.lab.add_node(f"client{i}", self.lab.images['ubuntu_ai_client'], x=200+100*i, y=500) for i in range(1, 10)]

        # 全互联 (Spine-Leaf Full Mesh)
        for s in spines:
            for l in leafs:
                self.lab.add_link(s, l)

        # Leaf 下挂设备
        self.lab.add_link(leafs[0], server)
        self.lab.add_link(leafs[1], clients[0]); self.lab.add_link(leafs[1], clients[1])
        self.lab.add_link(leafs[2], clients[2]); self.lab.add_link(leafs[2], clients[3])
        self.lab.add_link(leafs[3], clients[4]); self.lab.add_link(leafs[3], clients[5])
        self.lab.add_link(leafs[4], clients[6]); self.lab.add_link(leafs[4], clients[7])
        self.lab.add_link(leafs[5], clients[8])

        print("[Net] 部署物理拓扑...")
        self.deploy()
        time.sleep(20)
        
        print("[Net] 配置 OSPF 动态路由协议...")
        self.config(senario="ospf")
        time.sleep(20) # 节点变多，OSPF 收敛时间稍微拉长

    def start_real_inference(self):
        """在 server 启动真正的 CPU 推理服务"""
        server_ip = self.lab.get_host_ip("server")
        
        self.lab._run_cmd("server", "nohup tcpdump -i any -w /tmp/spine_leaf.pcap > /dev/null 2>&1 &")

        # (省略了冗长的 Base64 脚本转换与 Python 源码写入过程，保持与原来代码完全一致)
        real_llm_script = """
import os
import torch
from fastapi import FastAPI, Request
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import uvicorn

app = FastAPI()
MODEL_DIR = "/opt/models/tinyllama"

with open("/tmp/ai_boot.flag", "w") as f: f.write("booted\\n")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, local_files_only=True)
pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, device=-1)
with open("/tmp/ai_ready.flag", "w") as f: f.write("ready\\n")

@app.post("/v1/completions")
async def generate(request: Request):
    data = await request.json()
    outputs = pipe(data.get("prompt", ""), max_new_tokens=100, do_sample=True, temperature=0.7, return_full_text=False)
    return {"choices": [{"text": outputs[0]["generated_text"].strip()}]}

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=8000)
"""
        import base64
        b64_script = base64.b64encode(real_llm_script.encode("utf-8")).decode("utf-8")
        self.lab._run_cmd("server", f"bash -c 'echo {b64_script} | base64 -d > /tmp/real_llm.py'")
        self.lab._run_cmd("server", "bash -c 'rm -f /tmp/vllm_cpu.log /tmp/ai_ready.flag /tmp/ai_boot.flag /tmp/ai_pid'")

        print("[App] server 正在启动实时 CPU 推理引擎 (TinyLlama)...")
        start_cmd = "bash -c 'nohup python3 /tmp/real_llm.py > /tmp/vllm_cpu.log 2>&1 & echo $! > /tmp/ai_pid'"
        self.lab._run_cmd("server", start_cmd)

        print("[App] 等待 8000 端口响应...")
        for i in range(12):
            time.sleep(10)
            boot_flag = self.lab._run_cmd("server", "cat /tmp/ai_boot.flag")
            ready_flag = self.lab._run_cmd("server", "cat /tmp/ai_ready.flag")
            # 👇 注意这里把 client 改成了 client1
            check = self.lab._run_cmd("client1", f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:8000/v1/completions -d '{{\"prompt\":\"test\"}}' -H 'Content-Type: application/json'")

            if check == "200":
                print(f"[App] 推理服务已就绪！(第 {i*10} 秒)")
                break
            print(f"  ... 仍在加载模型 ({i*10}/120s)")

        prompt = '{"prompt": "Who are you?", "max_tokens": 50}'
        # 👇 注意这里把 client 改成了 client9，测试对角线最远端
        res = self.lab._run_cmd("client9", f"curl -s -X POST http://{server_ip}:8000/v1/completions -H 'Content-Type: application/json' -d '{prompt}'")
        print(f"\n[推理结果 (Client9)]:\n{res}")

if __name__ == "__main__":
    LAB = AIInference()
    LAB.start_real_inference()