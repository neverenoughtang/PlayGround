import time
from KlonetAPI import *
from base_netenv import NetworkEnvBase

class AIInference(NetworkEnvBase):
    def __init__(self, lab_name="ai_inference"):
        super().__init__(lab_name=lab_name)

        # ==========================================
        # 1. 构建 Spine-Leaf 拓扑 (4台路由器 + 2台主机)
        # ==========================================
        s1 = self.lab.add_node("spine1", self.lab.images["quagga"], x=400, y=100)
        s2 = self.lab.add_node("spine2", self.lab.images["quagga"], x=600, y=100)

        l1 = self.lab.add_node("leaf1", self.lab.images["quagga"], x=300, y=300)
        l2 = self.lab.add_node("leaf2", self.lab.images["quagga"], x=700, y=300)

        server = self.lab.add_node("server", self.lab.images['ubuntu_ai_server'], x=300, y=500)
        client = self.lab.add_node("client", self.lab.images['ubuntu_ai_client'], x=700, y=500)

        self.lab.add_link(s1, l1)
        self.lab.add_link(s1, l2)
        self.lab.add_link(s2, l1)
        self.lab.add_link(s2, l2)

        self.lab.add_link(l1, server)
        self.lab.add_link(l2, client)

        print("[Net] 部署物理拓扑...")
        self.deploy()
        time.sleep(20)
        
        print("[Net] 配置 OSPF 动态路由协议...")
        self.config(senario="ospf")
        time.sleep(15)

    def start_real_inference(self):
        """在 server 启动真正的 CPU 推理服务"""
        server_ip = self.lab.get_host_ip("server")
        
        # 1. 抓包准备
        self.lab._run_cmd("server", "nohup tcpdump -i any -w /tmp/spine_leaf.pcap > /dev/null 2>&1 &")

        # 2. 注入真实的 transformers CPU 推理脚本（离线加载固定目录模型）
        real_llm_script = """
import os
import torch
from fastapi import FastAPI, Request
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import uvicorn

app = FastAPI()
MODEL_DIR = "/opt/models/tinyllama"

# 启动标记：脚本已启动
with open("/tmp/ai_boot.flag", "w") as f:
    f.write("booted\\n")

print("正在从本地目录加载模型到 CPU...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_DIR,
    local_files_only=True
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    local_files_only=True
)

pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    device=-1
)

# readiness 标记：模型加载完成
with open("/tmp/ai_ready.flag", "w") as f:
    f.write("ready\\n")

@app.post("/v1/completions")
async def generate(request: Request):
    data = await request.json()
    raw_prompt = data.get("prompt", "")

    messages = [
        {"role": "system", "content": "You are a helpful and knowledgeable AI assistant."},
        {"role": "user", "content": raw_prompt},
    ]

    formatted_prompt = pipe.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    outputs = pipe(
        formatted_prompt,
        max_new_tokens=100,
        do_sample=True,
        temperature=0.7,
        return_full_text=False
    )

    generated_text = outputs[0]["generated_text"]

    return {
        "choices": [{"text": generated_text.strip()}]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

        import base64
        b64_script = base64.b64encode(real_llm_script.encode("utf-8")).decode("utf-8")
        
        # 写入推理脚本
        self.lab._run_cmd("server", f"bash -c 'echo {b64_script} | base64 -d > /tmp/real_llm.py'")

        # 启动前清理旧文件
        self.lab._run_cmd("server", "bash -c 'rm -f /tmp/vllm_cpu.log /tmp/ai_ready.flag /tmp/ai_boot.flag /tmp/ai_pid'")

        # 启动器检查
        model_dir_check = self.lab._run_cmd("server", "ls /opt/models/tinyllama")
        print(f"[Debug] 模型目录检查:\\n{model_dir_check}")
        config_check = self.lab._run_cmd("server", "cat /opt/models/tinyllama/config.json")
        print(f"[Debug] config.json 检查:\\n{config_check[:300]}")

        # 启动服务并记录 PID
        print("[App] server 正在启动实时 CPU 推理引擎 (TinyLlama)...")
        start_cmd = "bash -c 'nohup python3 /tmp/real_llm.py > /tmp/vllm_cpu.log 2>&1 & echo $! > /tmp/ai_pid'"
        self.lab._run_cmd("server", start_cmd)

        # 轮询探测
        print("[App] 等待 8000 端口响应 (CPU 加载较慢，约需 40s)...")
        for i in range(12):
            time.sleep(10)

            boot_flag = self.lab._run_cmd("server", "cat /tmp/ai_boot.flag")
            ready_flag = self.lab._run_cmd("server", "cat /tmp/ai_ready.flag")
            check = self.lab._run_cmd(
                "client",
                f"curl -s -o /dev/null -w '%{{http_code}}' http://{server_ip}:8000/v1/completions -d '{{\"prompt\":\"test\"}}' -H 'Content-Type: application/json'"
            )

            if check == "200":
                print(f"[App] 推理服务已就绪！(第 {i*10} 秒)")
                break

            boot_str = boot_flag.strip() if boot_flag and "No such file" not in boot_flag else "not_booted"
            ready_str = ready_flag.strip() if ready_flag and "No such file" not in ready_flag else "not_ready"
            print(f"  ... 仍在加载模型 ({i*10}/120s) | boot_flag={boot_str} | ready_flag={ready_str}")

        # 发起测试请求
        prompt = '{"prompt": "Who are you?", "max_tokens": 50}'
        res = self.lab._run_cmd(
            "client",
            f"curl -s -X POST http://{server_ip}:8000/v1/completions -H 'Content-Type: application/json' -d '{prompt}'"
        )
        print(f"\n[推理结果]:\n{res}")

        # ================= 排障专用代码 =================
        print("\n" + "="*40)
        print("🕵️ 深度排障信息采集开始...")

        # 1. 测试底层网络连通性
        ping_res = self.lab._run_cmd("client", f"ping -c 3 {server_ip}")
        print(f"\n[1. Client Ping Server 测试]:\n{ping_res}")

        # 2. 查看 8000 端口是否监听
        port_res = self.lab._run_cmd("server", "netstat -tuln | grep 8000")
        print(f"\n[2. Server 8000端口监听状态] (为空说明服务没起来):\n{port_res}")

        # 3. 查看 boot 文件
        boot_res = self.lab._run_cmd("server", "cat /tmp/ai_boot.flag")
        print(f"\n[3. AI Boot 文件状态] (为空说明脚本未真正启动):\n{boot_res}")

        # 4. 查看 readiness 文件
        ready_res = self.lab._run_cmd("server", "cat /tmp/ai_ready.flag")
        print(f"\n[4. AI Readiness 文件状态] (为空说明模型尚未完成初始化):\n{ready_res}")

        # 5. 查看服务 PID 文件
        pid_res = self.lab._run_cmd("server", "cat /tmp/ai_pid")
        print(f"\n[5. AI 服务 PID 文件]:\n{pid_res}")

        # 6. 提取 FastAPI 服务后台日志
        log_res = self.lab._run_cmd("server", "cat /tmp/vllm_cpu.log")
        print(f"\n[6. Server 内部运行日志]:\n{log_res}")

        print("="*40 + "\n")

if __name__ == "__main__":
    LAB = AIInference()
    LAB.start_real_inference()