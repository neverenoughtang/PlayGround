FROM ubuntu:22.04

# 避免交互式配置卡住构建
ENV DEBIAN_FRONTEND=noninteractive

# 1. 安装基础网络与排障工具
RUN apt-get update && apt-get install -y \
    python3-pip python3-dev python3-venv \
    curl net-tools iproute2 iputils-ping tcpdump iptables stress-ng apache2-utils vim \
    && rm -rf /var/lib/apt/lists/*

# 2. 设置工作目录
WORKDIR /app

# 3. 安装 AI 推理与分布式通信依赖包
# 注意：这里专门安装 vllm 的 CPU 版本以适配虚拟网络平台
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip3 install --no-cache-dir ray transformers fastapi uvicorn && \
    pip3 install --no-cache-dir vllm

# 4. 预下载小模型 (可选，建议在构建镜像时下载好，节约运行时带宽)
# 运行一段 python 脚本拉取 TinyLlama
RUN python3 -c "from transformers import AutoTokenizer, AutoModelForCausalLM; \
    AutoTokenizer.from_pretrained('TinyLlama/TinyLlama-1.1B-Chat-v1.0'); \
    AutoModelForCausalLM.from_pretrained('TinyLlama/TinyLlama-1.1B-Chat-v1.0')"

CMD ["/bin/bash"]