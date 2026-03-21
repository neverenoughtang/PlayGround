import os
import re
from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 自动向上寻找 .env 文件并加载

from service.klonet import KlonetTCAPI  # 替换为你的底层命令执行API

mcp = FastMCP("KlonetLinkServer", log_level="ERROR")

@mcp.tool()
def check_link_quality(host: str, target_ip: str) -> str:
    """
    用户投诉网络卡顿、慢、丢包或延迟高时，检查底层链路质量.
    通过 tc qdisc show 检查设备上是否被人为注入了延迟(latency)、丢包(loss)、抖动(jitter)或带宽限制(bandwidth).
    
    Args:
        host: 待检查的节点名 (如 h1 等)
        target_ip: 待检查的目标 IP (如 192.168.3.17)
    """
    lab = os.getenv("LAB_NAME")
    API = KlonetTCAPI(lab) # 注意替换为你实际的 API 实例
    
    # 1. 获取 TC 规则
    raw_output = API._run_cmd(host, "tc qdisc show")
    # 2. 执行 Ping (发 10 个包，超时时间 2 秒)
    ping_output = API._run_cmd(host, f"ping -c 10 -W 2 {target_ip}")
    
    # 构建最终返回的报告
    result = f"【TC 规则输出】\n{raw_output}\n"
    result += f"\n【Ping 测试输出】\n{ping_output}\n"
    
    diagnosis_hint = ""
    
    # 提取丢包率
    loss_match = re.search(r'(\d+)% packet loss', ping_output)
    loss_rate = float(loss_match.group(1)) if loss_match else 0.0
    
    # 提取 rtt 数据: min/avg/max/mdev
    mdev = 0.0
    avg_rtt = 0.0
    rtt_match = re.search(r'= ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms', ping_output)
    if rtt_match:
        avg_rtt = float(rtt_match.group(2))
        mdev = float(rtt_match.group(4))

    # 提取限制带宽 rate 参数的值
    rate_match = re.search(r'rate\s+([0-9a-zA-Z]+)', raw_output)
    rate_val = rate_match.group(1) if rate_match else "Unknown"

    # 诊断逻辑
    if raw_output:
        # 0. 误诊
        if loss_rate == 100.0:
            diagnosis_hint += (
                "\n⚠️ 【防误判锁】Ping 出现了 100% 丢包，但 TC 规则里并没有 'loss' 参数！\n"
                "绝不是 link_loss 故障！数据包可能被路由黑洞吃掉、被防火墙 DROP 或者是路由不通。请去查路由和数据面等！"
            )
        # 1. 丢包
        if loss_rate > 0 and loss_rate < 100.0: 
            diagnosis_hint += f"\n[专家提示] 检测到丢包率为 {loss_rate}% > 0%。\n🎯 确诊：被注入了丢包故障！请直接调用 submit_diagnosis 提交 link_loss。"
        # 2. 抖动
        elif mdev > 10.0: 
            # 局域网正常 mdev 只有零点几毫秒，大于 10ms 绝对是人为抖动
            diagnosis_hint += f"\n[专家提示] 检测到 Ping 延迟极度不稳定 (平均偏差 mdev = {mdev} ms)。\n🎯 确诊：被注入了抖动故障！请直接调用 submit_diagnosis 提交 link_jitter。"
        # 3. 延迟高
        elif avg_rtt > 50.0:
            # 延迟高，但 mdev 小，说明是稳定延迟
            diagnosis_hint += f"\n[专家提示] 检测到 Ping 延迟极高但很稳定 (平均延迟 avg = {avg_rtt} ms, 抖动 mdev = {mdev} ms)。\n🎯 确诊：被注入了高延迟故障！请直接调用 submit_diagnosis 提交 link_latency。"
        # 4. 带宽
        elif "tbf" in raw_output:
            diagnosis_hint += f"\n[专家提示] 检测到带宽很小 (速度 rate = {rate_val})。\n🎯 确诊：被注入了限制带宽故障！请直接调用 submit_diagnosis 提交 link_bandwidth。"
        else:
            diagnosis_hint += "\n[专家提示] 未发现 netem/tbf 规则。"
    # 5. 没有规则
    else:
        diagnosis_hint += "\n[专家提示] 未发现 netem/tbf 规则。"
        
    return raw_output + diagnosis_hint

if __name__ == "__main__":
    # 启动 FastMCP 服务，默认基于 stdio(标准输入输出) 与 Agent 通信
    mcp.run(transport="stdio")