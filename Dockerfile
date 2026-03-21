# 1. 基础镜像：选择轻量级的 Python 环境 (假设你用的是 3.10，如果不是请将 3.10 改成你的版本)
FROM python:3.12-slim

# 2. 设置容器内的工作目录 (相当于在小房间里建了一个 /app 文件夹)
WORKDIR /app

# 3. 巧妙利用缓存：先复制依赖清单并安装
COPY requirements.txt .
# 使用 pip 安装依赖 (由于我们在干净的容器里，不需要 uv 也能快速安装，主打一个稳定)
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制项目的所有代码到容器的 /app 目录下
COPY . .

# 5. 启动命令：告诉容器启动时执行什么指令
# 假设你的智能体入口文件是 main.py，如果是其他名字请修改这里
CMD ["python", "main.py"]