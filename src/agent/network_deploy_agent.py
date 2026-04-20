import asyncio
import os
import sys
import time
import subprocess
from typing import TypedDict
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

# --- 路径环境配置 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, ".."))
project_root = os.path.abspath(os.path.join(src_dir, ".."))
playground_dir = os.path.abspath(os.path.join(src_dir, "playground"))

if src_dir not in sys.path: sys.path.insert(0, src_dir)
if project_root not in sys.path: sys.path.append(project_root)
if playground_dir not in sys.path: sys.path.insert(0, playground_dir)

# 导入本地模型加载器
from utils.llm_models import load_model
# 导入 KlonetBaseAPI 用于获取拓扑信息
from mcp_server.klonet_base_api import KlonetBaseAPI
# 导入全局预热系统
from diagnose_agent.tools import prewarm_diagnose_caches
from fault_inject_agent import prewarm_inject_caches

# ==========================================
# 辅助函数: 精简拓扑信息算法 + 全局预热
# ==========================================
def simplify_topo(lab_name: str, raw_topo: dict) -> str:
    """
    接收全量的拓扑 JSON 字典，过滤掉所有非网络特性的冗余参数，
    仅保留节点(名称/类型/接口/IP/网关)和链路(源/目的及对应IP)。
    """
    simplified = []
    simplified.append(f"{lab_name} 的拓扑信息:")
    
    # 1. 提炼节点信息
    simplified.append("[节点列表]")
    categories = ['controllers', 'hosts', 'routers', 'switches', 'dpdks']
    for category in categories:
        if category not in raw_topo or not raw_topo[category]:
            continue
            
        for node_name, node_info in raw_topo[category].items():
            # 基础网络属性
            node_type = node_info.get('type', category)
            
            # 👇 【新增修复】：智能推断节点真实类型 (覆盖分类不准的情况)
            image_name = node_info.get('image_name', '').lower()
            subtype = node_info.get('subtype', '').lower()
            
            if 'ryu' in image_name or 'ryu' in subtype:
                node_type = 'ryu'
            elif 'bmv2' in image_name or 'bmv2' in subtype or 'p4' in image_name:
                node_type = 'bmv2'
            # 👆 =======================================================
            
            gateway = node_info.get('gateway', '')
            interfaces = node_info.get('interfaces', [])
            
            # 格式化接口
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')

                # 修复：安全解析子网掩码，防止空字符串或非法格式导致 int() 报错
                netmask = iface.get('netmask', '') 
                mask = ""
                if netmask and '.' in netmask:
                    try:
                        mask_len = sum(bin(int(x)).count('1') for x in netmask.split('.'))
                        mask = f"/{mask_len}"
                    except ValueError:
                        mask = "" # 如果解析失败，就不带掩码后缀

                # 修正接口名称：如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname

                # 加上 IP
                if ip:
                    iface_strs.append(f"{actual_iname}({ip}{mask})")
                else:
                    iface_strs.append(f"{actual_iname}")
            
            # 拼接单节点信息
            # 这里的 [node_type] 就会根据上面的智能推断显示出 [ryu] 或 [bmv2]
            info_str = f"- {node_name} [{node_type}]"
            if iface_strs:
                info_str += f" | 接口: {', '.join(iface_strs)}"
            if gateway:
                info_str += f" | 默认网关: {gateway}"
                
            simplified.append(info_str)
            
    # 2. 提炼链路信息 (原代码保持不变)
    simplified.append("\n[链路]")
    links = raw_topo.get('links', {})
    for link_name, link_info in links.items():
        src = link_info.get('source', '')
        src_ip = link_info.get('sourceIP', '')
        tgt = link_info.get('target', '')
        tgt_ip = link_info.get('targetIP', '')
        
        # 移除掩码后缀(如 /24)，保持视觉清爽
        src_ip_clean = src_ip.split('/')[0] if src_ip else ""
        tgt_ip_clean = tgt_ip.split('/')[0] if tgt_ip else ""
        
        src_str = f"{src}({src_ip_clean})" if src_ip_clean else src
        tgt_str = f"{tgt}({tgt_ip_clean})" if tgt_ip_clean else tgt
        
        simplified.append(f"- 链路 {link_name}: {src_str} <---> {tgt_str}")
        
    return "\n".join(simplified)

# ==========================================
# 1. 状态定义与 LLM 输出结构
# ==========================================
class DeployState(TypedDict):
    user_query: str        # 用户需求输入
    deploy_model: str      # 调用的 LLM 模型名称
    lab_name: str          # 经 LLM 决策后选中的拓扑脚本名称 (例如 "ospf_enterprise")
    deploy_status: str     # 部署执行的结果状态说明
    netenv_info: str       # 最终生成的精简网络拓朴信息

class TopologySelection(BaseModel):
    """强制 LLM 输出的结构化数据，用于精准提取所选拓扑名称"""
    lab_name: str = Field(description="选中的网络拓朴名称，必须严格从提供的 7 个英文名称中选择其一。")
    reasoning: str = Field(description="选择该拓朴的简要理由。")

# ==========================================
# 2. 智能体节点对象 (Nodes)
# ==========================================
class DeployAgent:
    """
    网络拓朴部署决策智能体：分析用户需求并选择正确的拓扑脚本
    """
    def __init__(self, backend_model: str = "qwen3.5-small"):
        self.llm = load_model(backend_model=backend_model)
        # 使用 structured_output 强制输出 TopologySelection 的 JSON 格式
        self.structured_llm = self.llm.with_structured_output(TopologySelection)
        
    async def analyze_requirement(self, user_query: str) -> dict:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", 
"""你是一位资深的网络平台架构专家，负责依据用户的自然语言需求，为其分配合适的底层网络拓扑。

当前系统支持以下 7 种预设网络拓朴（必须严格输出其英文名）：
1. static_routing：静态路由，包含主机、交换机、路由器的标准三层网络。
2. simple_bgp：BGP协议网络，胖树架构，用于跨域路由模拟。
3. ospf_enterprise：OSPF协议网络，适用大型企业网模拟。
4. rip_internet：RIP协议网络，适用小型企业网模拟。
5. p4_star：使用 bmv2 交换机模拟三层路由器的星型网络，可编程数据面，节点较少。
6. sdn_openflow：SDN架构，Ryu控制器为主(master)，下发流表至主 OVS，主 OVS 控制 3个从 OVS 的二层网络。
7. ai_inference：Spine-Leaf 结构，包含 server 和 client，利用 FastAPI 模拟 HTTP 请求进行 LLM 推理的网络。

请根据用户的需求，选出最贴切的一个拓扑名称。
"""),
            ("user", "用户需求：{user_query}")
        ])
        
        chain = prompt_template | self.structured_llm
        
        try:
            print("[Deploy Agent] 🧠 正在思考应该分配哪个网络拓扑...")
            result: TopologySelection = await chain.ainvoke({"user_query": user_query})
            print(f"[Deploy Agent] 🎯 决策完成: 选择了 '{result.lab_name}'。\n理由: {result.reasoning}")
            return {"lab_name": result.lab_name, "reasoning": result.reasoning}
        except Exception as e:
            print(f"[Deploy Agent] ❌ LLM 决策失败: {e}")
            # 兜底容错，默认返回基础的静态路由
            return {"lab_name": "static_routing", "reasoning": "LLM 解析异常，使用默认兜底拓扑。"}

# --- Graph Node 函数 ---
async def analyze_node(state: DeployState):
    """
    【用户意图解析】
    分析需求并确定 lab_name
    """
    deployer = DeployAgent(backend_model=state.get("deploy_model", "qwen3.5-small"))
    res = await deployer.analyze_requirement(state["user_query"])
    return {"lab_name": res["lab_name"]}

async def prewarm_systems_node(state: DeployState):
    """
    【全局极速预热】
    在等待用户输入期间，后台拉起所有 MCP 容器接口、载入各类大模型向量库。
    利用 asyncio.gather 并发预热诊断和注入模块，将冷启动时间压缩到极致！
    """
    lab_name = state["lab_name"]

    if lab_name:
        try:
            print("\n[System] 🔄 正在后台执行全局极速预热 (RAG / MCP / NLP)...")
            # 【核心修改】并发执行预热，提升启动速度
            await asyncio.gather(
                prewarm_inject_caches(lab_name),
                prewarm_diagnose_caches(lab_name)
            )
            print("[System] ✅ 全局系统极速预热完毕，等待指令发车！")
        except Exception as e:
            print(f"[Error] ❌ 预热失败: {e}")

    return {} # 预热只产生副作用（修改全局缓存），不改变图的状态字典

async def execute_deploy_node(state: DeployState):
    """
    【物理部署拓扑】
    收集简化的 netenv_info
    """
    lab_name = state["lab_name"]
    os.environ["LAB_NAME"] = lab_name # 设置环境变量以供 Klonet 等底层框架读取
    
    print(f"\n[System] 🛠️ 开始部署网络拓扑脚本: {lab_name}.py ...")
    
    # 假设所有拓扑脚本均存放在 src/net_env 目录下
    cwd = os.path.abspath(os.path.join(src_dir, "net_env"))
    cmd = ["uv", "run", f"{lab_name}.py"]
    
    try:
        # 1. 创建异步子进程
        process = await asyncio.create_subprocess_exec(
            *cmd, 
            cwd=cwd, 
            # PIPE 的意思是建立一根“管道”，
            # 加了之后，子进程的输出会流进这根管道，等待 Python 读取。
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        
        # 2. 与子进程进行“通信”并等待其结束 (最核心的一步)，类似“对讲机”
        # .communicate() 做了三件事：
        #   a. 不断地从 stdout 和 stderr 的管道里把数据读出来（防止管道塞满导致子进程卡死）。
        #   b. 异步等待 (await)，直到子进程彻底运行结束并退出。
        #   c. 此时事件循环会切走，把 CPU 让给其他需要的协程。
        _, stderr_bytes = await process.communicate()
        
        # 3. 检查子进程的退出状态码 (Return Code)
        if process.returncode != 0:
            # ⚠️ 【Bug 修复点】：
            # process.stderr 是一个 StreamReader 对象，直接打印是一串内存地址！
            # 真正捕获到的报错字符串，是上面 communicate() 返回的 stderr_bytes。
            # 且因为它是 bytes 字节流，需要 decode() 解码成字符串。
            error_msg = f"拓扑部署失败，执行脚本出错:\n{stderr_bytes.decode('utf-8')}"
            print(f"[Error] ❌ {error_msg}")
            return {
                "deploy_status": "Fatal",
                "netenv_info": f"部署失败: {error_msg}"
            }
            
        print(f"[System] ✅ 脚本 {lab_name}.py 执行完成！拓扑成功部署")
        await asyncio.sleep(3)
        
        # 部署成功后，通过 KlonetBaseAPI 获取全量拓扑信息
        print(f"[System] 📡 正在通过 Klonet API 抓取 '{lab_name}' 的全量拓扑结构...")
        api = KlonetBaseAPI(lab_name)
        # 丢进底层线程池
        raw_topo_dict = await asyncio.to_thread(api.get_topo_json) # 传入引用，不能带括号!   
        
        # 将数十 KB 的无用 JSON 数据精简为几十行 LLM 友好的纯文本
        netenv_info = simplify_topo(lab_name, raw_topo_dict)
        
        print(f"--- 拓扑结构如下 --- \n{netenv_info}")

        return {
            "deploy_status": "Successful",
            "netenv_info": netenv_info
        }
        
    except Exception as e:
        error_msg = f"物理部署期间发生严重异常: {e}"
        print(f"[Error] ❌ {error_msg}")
        return {
            "deploy_status": "Exception",
            "netenv_info": error_msg
        }

# ==========================================
# 3. 构建 LangGraph 工作流
# ==========================================
def build_deploy_graph():
    """
    组装部署工作流 (带极速并发优化)

                START
                  |
             analyze_node (大模型决策 lab_name)
                |    |  <-- 【并发分发】
            |            | 
execute_deploy_node  prewarm_systems_node (拉起底层MCP/向量库模型)
            |            |
                |    |  <-- 【并发汇聚】
                  END
    """
    workflow = StateGraph(DeployState)
    
    # 添加节点
    workflow.add_node("analyze_node", analyze_node)
    workflow.add_node("execute_deploy_node", execute_deploy_node)
    workflow.add_node("prewarm_systems_node", prewarm_systems_node) # 注册新增的预热节点

    # 构建有向边
    workflow.add_edge(START, "analyze_node")

    # analyze_node 结束后，兵分两路，引擎会自动并发执行这两个节点
    workflow.add_edge("analyze_node", "execute_deploy_node")
    workflow.add_edge("analyze_node", "prewarm_systems_node")
    
    # 两路都执行完毕后，图才会流向 END，完美实现木桶效应兜底
    workflow.add_edge("execute_deploy_node", END)
    workflow.add_edge("prewarm_systems_node", END)
    
    return workflow.compile()

# ==========================================
# 4. 本地测试入口
# ==========================================
if __name__ == "__main__":
    async def test():
        # 1. 初始化编译图
        graph = build_deploy_graph()
        
        # 2. 模拟外部输入 
        initial_state = {
            "user_query": "我需要一个p4网络",
            "deploy_model": "qwen3.5-small",
            "lab_name": "",
            "deploy_status": "",
            "netenv_info": ""
        }
        
        print("="*60)
        print("🚀 [DeployGraph] 拓扑部署 Agent 测试启动")
        print("="*60)
        
        # 3. 运行工作流
        final_state = await graph.ainvoke(initial_state)
        
        # 4. 展示存入 state 的最终结果
        print("\n" + "="*60)
        print("🎯 [DeployGraph] 运行结束！最终 State 状态提取如下：")
        print(f"✅ 选定拓扑 (lab_name): {final_state['lab_name']}")
        print(f"✅ 部署状态: {final_state['deploy_status']}")
        print(f"✅ 精简后的网络拓扑环境信息 (netenv_info):\n{final_state['netenv_info']}")
        print("="*60)

    asyncio.run(test())