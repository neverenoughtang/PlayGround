import sys
import os
import traceback
import asyncio
import time
from typing import List, Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError
from langchain_mcp_adapters.client import MultiServerMCPClient

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 导入本地模型加载器和日志
from utils.llm_models import load_model


# ==========================================
# Agent 最终结果提交通道
# ==========================================
@tool
def submit_diagnosis(root_cause: str) -> str:
    """
    当且仅当你排查确定了最终的根本原因时，必须调用此工具。
    输入参数 root_cause 必须严格是提示词中规定的那几类英文字符串之一。
    调用此工具标志着你的诊断任务结束。
    """
    return f"[DIAGNOSIS_COMPLETED]: {root_cause}"


class NetworkFaultDiagnosisAgent:
    """
    网络故障诊断智能体
    """

    def __init__(self, lab_name: str, max_steps: int, netenv_info: str, problem_info: str, backend_model: str = "qwen3.5-27b"):
        self.lab_name = lab_name  # 🌟 新增：显式保存当前测试的场景名
        self.max_steps = max_steps
        self.netenv_info = netenv_info
        self.problem_info = problem_info
        self.backend_model = backend_model
        
        # 加载 LLM 和 系统提示词
        self.llm = load_model(backend_model=self.backend_model)
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        SYSTEM_PROMPT = \
        f"""你是一名专业的网络故障诊断专家。

【当前网络场景】
{self.netenv_info}

【当前故障】
{self.problem_info}

严格遵循 ReAct 框架诊断网络故障。注意你只有 {self.max_steps} 次尝试机会!

【专家经验】
- 防Ping陷阱：
  如果用户投诉“网络卡顿、慢” 或者 “不稳定”，但你发现 Ping 测试竟然是 0% 丢包且低延迟，不要被骗了！
  必须立刻使用 `check_link_bandwidth` 或 `check_cpu_overload` 检查主机 CPU占用，或核心路由器或网关的带宽限制规则！
- 二层/三层网络隔离法则（极其重要！）：
  1. 仅在 static_routing, simple_bgp, ospf_enterprise, rip_internet 场景（包含 r1, r2 路由器）中，才能使用 `check_routing_table` 和 `check_data_plane_drop` 查路由和防火墙！
  2. 对于 sdn_openflow 和 p4_star 场景，节点 s0, s1, s2 等都是二层交换机，绝对没有三层 IP 路由表！严禁在它们上面查路由，否则会得到 "Network is unreachable" 的假象！
- SDN 路径追踪法则：
  在 sdn_openflow 场景中如果 Ping 不通，并且检查第一个交换机发现控制器连接正常且流表正常，**千万不要放弃！** 故障很可能发生在接入层交换机（例如连接 Host 的 s1, s2等）。你必须依次调用 `check_ovs_status` 检查链路途经的**所有交换机**，直到找出流表丢失 (drop) 或 控制器断开 (is_connected 消失) 的节点。

【工作流规范】
1. Observation (观察现象)：分析当前网络状态、存在故障和之前的工具返回信息;
2. Thought (思考假设)：基于已有信息，提出可能的故障原因，并计划下一步的排查动作;
3. Action (调用工具)：一次调用 1 个适当的 MCP 工具来验证你的假设; 
4. 循环上述过程最多 {self.max_steps} 次，找到根本原因，次数用完的话就直接提交你认为的最可能的结果就行;
5. 提交结果：确定根本原因后，必须且仅调用一次 `submit_diagnosis` 工具来结束任务。

【网络场景说明】
1. static_routing: 静态路由, 可能发生主机侧故障、物理链路故障、通用 frr 故障(优先考虑)
2. simple_bgp: 简单 BGP 网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、bgp协议故障(优先考虑)
3. ospf_enterprise: OSPF 企业网, 可能发生主机侧故障、物理链路故障、通用 frr 故障、ospf协议故障(优先考虑)
4. rip_internet: rip 小型网络, 可能发生主机侧故障、物理链路故障、通用 frr 故障、rip协议故障(优先考虑)
5. sdn_openflow: sdn 网络, 可能发生主机侧故障、物理链路故障、ovs或ryu故障(优先考虑)
6. p4_star: P4 星型网络, 可能发生主机侧故障、物理链路故障、p4-bmv2故障(优先考虑)

【根本原因说明】
你必须且仅能从以下 3 大类中选择一个最符合的英文字符串作为最终诊断结果提交。请仔细区分故障发生的载体（是主机配置出错，还是中间的路由器/交换机出错）：

1. 主机侧故障 (Host Faults) - 仅限端主机(Host)自身的配置问题：
  - ip_misconfig: 主机网卡 IP 地址或子网掩码配置错误、甚至未配置
  - default_route_missing: 主机自身的路由表中缺少默认网关路由(default via)
  - arp_poisoning: 主机自身的 ARP 缓存表被投毒，网关 MAC 地址被恶意篡改
  - interface_down: 主机的物理或逻辑网络接口处于 DOWN 状态
  - dns_error: 主机的 DNS 服务器配置错误，导致无法解析域名
  - high_cpu_load: 主机 CPU 占用率极高（如满载），导致发包或处理极慢

2. 核心网络服务故障 (Service Faults) - 发生在中间节点(Router/Switch)上的路由协议或数据面问题：
(1) 通用 frr 故障:
  - route_missing: 路由器(Router)的全局路由表中丢失了去往目标网段的路由
  - static_route_blackhole: 路由器上被人为配置了去往目标网段的黑洞路由 (blackhole)
  - router_data_plane_drop: 路由器的防火墙或 iptables 规则 (FORWARD链) 强行 DROP/REJECT 了转发流量
(2) bgp协议故障(仅针对 simple_bgp 场景):
  - bgp_neighbor_shutdown: 路由器的 BGP 邻居关系被断开/关闭 (Active/Idle状态)
  - bgp_withdraw_route: BGP 路由撤销，导致 BGP 表中无目标路由
  - bgp_wrong_peer_asn: BGP 邻居的 AS 号配置错误导致无法建联
(3) ospf协议故障(仅针对 ospf_enterprise 场景):
  - ospf_passive_interface: 路由器的接口被设置为 OSPF 被动接口，停止发送 Hello 包
  - ospf_cost_spike: OSPF 接口的开销 (Cost) 被恶意调得极高，导致流量绕路或中断
  - ospf_daemon_crash: 路由器的 OSPF 进程崩溃退出
(4) rip协议故障(仅针对 rip_internet 场景):
  - rip_passive_interface: 路由器的接口被设置为 RIP 被动接口，停止发送更新
  - rip_route_filter: 路由器被恶意配置了 distribute-list 规则，强行过滤了路由发布
  - rip_metric_offset: 路由器被恶意配置了 offset-list，大幅篡改路由跳数导致不可达
(5) ovs或ryu故障(仅针对 sdn_openflow 场景):
  - sdn_controller_crash: SDN 控制器(Ryu)宕机或断开连接
  - ovs_disconnect_controller: OpenvSwitch 与 SDN 控制器断开连接
  - ovs_global_drop_flow: OpenvSwitch 被下发了全局 Drop 所有流表
(6) p4-bmv2故障(仅针对 p4_star 场景):
  - bmv2_process_crash: P4 Bmv2 交换机进程崩溃
  - p4_table_drop: P4 交换机匹配到丢弃流表项
  - p4_wrong_forwarding: P4 交换机转发逻辑或端口映射错误

3. 物理链路故障 (Link Faults) - 连接各节点之间的网线/通道质量恶化：
  - link_latency: 链路上被人为注入了异常高且稳定的延迟
  - link_loss: 链路存在明显的报文丢包率 (Packet Loss > 0%)
  - link_jitter: 链路延迟极不稳定，出现严重抖动 (Jitter/mdev 很大)
  - link_bandwidth: 链路可用带宽被严格限制 (如 TBF 限速)，导致大流量严重拥堵

【严禁行为】
- ⚠️ 得出最终的故障结论时，绝不能只把答案写在你的思考(Thought)中！必须调用 `submit_diagnosis` 工具并传入根本原因，只有这样系统才能接收到你的答案！
- 遇到信息不足时，务必先通过工具查询状态，绝不可随意猜测
- 次数很多，切不可仅用一个工具就下定论！
- 切勿一次性调用大量不相关的工具，应按照逻辑链条一步一步排查
- 所有工具输出结果都是稳定正确的，同样的工具+同样的输入参数切勿调用两次以上！
"""
        return SYSTEM_PROMPT

    async def run_diagnosis(self, query: str = "根据信息排查故障。使用 submit_diagnosis 提交结果。", timeout: int = 1200) -> Dict[str, Any]:
        
        # # 将提示词块合并打印
        # init_log = (
        #     f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        #     f"┃ 📜 [System Prompt / 智能体记忆初始化]                                ┃\n"
        #     f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        #     f"{self.system_prompt}\n"
        #     f"{'='*70}"
        # )
        # print(init_log)
        print(f"Agent starting diagnosis task... (Max Steps: {self.max_steps})")
        
        # --- 性能与轨迹追踪初始化 ---
        start_time = time.perf_counter()
        tool_call_count = 0
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        trajectory_log = [] # 记录完整推理与工具执行流
        final_result = "unknown_error"
        
        mcp_server_dir = os.path.join(src_dir, "service", "mcp_server")
        server_files = [
            "klonet_link_server", "klonet_host_server", 
            "klonet_frr_server", "klonet_switch_server", "klonet_controller_server"
        ]
        
        # 克隆当前系统环境，并强行覆写 LAB_NAME
        custom_env = os.environ.copy()
        custom_env["LAB_NAME"] = self.lab_name 
        
        connections = {}
        for s_file in server_files:
            server_path = os.path.join(mcp_server_dir, f"{s_file}.py")
            if os.path.exists(server_path):
                connections[s_file] = {
                    "command": sys.executable,  
                    "args": [server_path],
                    "transport": "stdio",
                    "env": custom_env  # 🌟 将强化后的环境变量字典传给子进程
                }

        client = MultiServerMCPClient(connections)
        
        try:
            print("Loading tools from all MCP Servers... (Please wait)\n")
            server_tools = await client.get_tools()
            tools = [submit_diagnosis] + server_tools
            
            agent_executor = create_agent(model=self.llm, tools=tools)

            inputs = {
                "messages": [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=query)
                ]
            }
            
            config = {"recursion_limit": self.max_steps}

            # 把整个 AI 推理流程打包成异步任务
            async def _process_stream():
                # 👇 新增这一行：声明我们要修改外部的这两个基础变量
                nonlocal tool_call_count, final_result

                async for chunk in agent_executor.astream(inputs, config=config, stream_mode="values"):
                    last_msg = chunk["messages"][-1]
                    
                    if last_msg.type == "human":
                        continue
                    
                    # 💡 Token 统计 (累加每个 chunk 的消耗)
                    if hasattr(last_msg, 'usage_metadata') and last_msg.usage_metadata:
                        token_usage["input_tokens"] += last_msg.usage_metadata.get("input_tokens", 0)
                        token_usage["output_tokens"] += last_msg.usage_metadata.get("output_tokens", 0)
                        token_usage["total_tokens"] += last_msg.usage_metadata.get("total_tokens", 0)

                    # 记录 AI 的 Thought 和 Action
                    if last_msg.type == "ai":
                        if last_msg.content:
                            t_content = last_msg.content.strip()
                            log_str = f"🤔 [Thought]: {t_content}"
                            trajectory_log.append(log_str)
                            print(log_str)
                        
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                tool_call_count += 1
                                t_name = tc['name']
                                t_args = tc['args']
                                log_str = f"🛠️ [Action]: Call '{t_name}' with {t_args}"
                                trajectory_log.append(log_str)
                                print(log_str)

                    # 记录 Tool 的 Observation
                    elif last_msg.type == "tool":
                        t_name = last_msg.name
                        raw_content = last_msg.content
                        clean_text = str(raw_content)
                        if isinstance(raw_content, list) and len(raw_content) > 0 and isinstance(raw_content[0], dict):
                            clean_text = raw_content[0].get('text', str(raw_content))
                        clean_text = clean_text.strip()
                        
                        log_str = f"👁️ [Observation from {t_name}]: {clean_text}"
                        trajectory_log.append(log_str)
                        print(log_str)

                        if t_name == "submit_diagnosis" and "DIAGNOSIS_COMPLETED" in clean_text:
                            final_result = clean_text.split(":")[-1].strip()
                            log_str = f"📕 [Submission]: {final_result}"
                            trajectory_log.append(log_str)
                            print(log_str)

            await asyncio.wait_for(_process_stream(), timeout=timeout)

        # 【在原有的 except GraphRecursionError: 前方，新增一个超时异常捕获】:
        except asyncio.TimeoutError:
            log_str = f"\n⚠️  [Agent 中断]: 诊断流程执行超时 ({timeout} 秒)！"
            final_result = "timeout"
            trajectory_log.append(log_str)
            print(log_str)

        except GraphRecursionError:
            log_str = f"⚠️ [Error]: Reached max steps limit ({self.max_steps})."
            final_result = "max_steps_reached"
            trajectory_log.append(log_str)
            print(log_str)
            
        except Exception as e:
            final_result = "unknown_error"
            trajectory_log.append(f"❌ [Error]: Exception occurred - {e}")
            print(f"【详细错误追踪】:\n{traceback.format_exc()}")
            
        finally:
            execution_time = time.perf_counter() - start_time
            
        return {
            "result": final_result,
            "trajectory": "\n".join(trajectory_log),
            "tool_call_count": tool_call_count,
            "execution_time": round(execution_time, 2),
            "token_usage": token_usage
        }