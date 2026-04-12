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

# ==========================================
# 辅助函数: 精简拓扑信息算法
# ==========================================
def simplify_topo(lab_name: str, raw_topo: dict) -> str:
    """
    接收全量的拓扑 JSON 字典，过滤掉所有非网络特性的冗余参数，
    仅保留节点(名称/类型/接口/IP/网关)和链路(源/目的及对应IP)。
    """
    simplified = []
    simplified.append(f"\n {lab_name} 的拓扑信息:")
    
    # 1. 提炼节点信息
    simplified.append("\n[节点列表]")
    categories = ['controllers', 'hosts', 'routers', 'switches', 'dpdks']
    for category in categories:
        if category not in raw_topo or not raw_topo[category]:
            continue
            
        for node_name, node_info in raw_topo[category].items():
            # 基础网络属性
            node_type = node_info.get('type', category)
            gateway = node_info.get('gateway', '')
            interfaces = node_info.get('interfaces', [])
            
            # 格式化接口
            iface_strs = []
            for iface in interfaces:
                ip = iface.get('ip', '')
                raw_iname = iface.get('name', 'ethX')
                netmask = iface.get('netmask', '/24') 
                mask = f"/{sum(bin(int(x)).count('1') for x in netmask.split('.'))}" # 掩码

                # 修正接口名称：如果接口名以节点名开头 (如 h1s1_1)，则去掉节点名，加上 'to'
                if raw_iname.startswith(node_name):
                    actual_iname = "to" + raw_iname[len(node_name):]
                else:
                    actual_iname = raw_iname

                if ip:
                    iface_strs.append(f"{actual_iname}({ip}{mask})")
                else:
                    iface_strs.append(f"{actual_iname}")
            
            # 拼接单节点信息
            info_str = f"- {node_name} [{node_type}]"
            if iface_strs:
                info_str += f" | 接口: {', '.join(iface_strs)}"
            if gateway:
                info_str += f" | 默认网关: {gateway}"
                
            simplified.append(info_str)
            
    # 2. 提炼链路信息
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
    def __init__(self, backend_model: str = "qwen3.5-27b"):
        self.llm = load_model(backend_model=backend_model)
        # 使用 structured_output 强制输出 TopologySelection 的 JSON 格式
        self.structured_llm = self.llm.with_structured_output(TopologySelection)
        
    async def analyze_requirement(self, user_query: str) -> dict:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", 
"""你是一位资深的网络平台架构专家，负责依据用户的自然语言需求，为其分配合适的底层网络拓扑。

当前系统支持以下 7 种预设网络拓朴（必须严格输出其英文名）：
1. static_routing：静态路由，包含主机、交换机、路由器的标准三层网络。
2. simple_bgp：BGP协议网络，用于跨域路由模拟。
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
            print("[DeployAgent] 🧠 正在思考应该分配哪个网络拓扑...")
            result: TopologySelection = await chain.ainvoke({"user_query": user_query})
            print(f"[DeployAgent] 🎯 决策完成: 选择了 '{result.lab_name}'。\n理由: {result.reasoning}")
            return {"lab_name": result.lab_name, "reasoning": result.reasoning}
        except Exception as e:
            print(f"[DeployAgent] ❌ LLM 决策失败: {e}")
            # 兜底容错，默认返回基础的静态路由
            return {"lab_name": "static_routing", "reasoning": "LLM 解析异常，使用默认兜底拓扑。"}

# --- Graph Node 函数 ---

async def analyze_node(state: DeployState):
    """
    节点1：分析需求并确定 lab_name
    """
    deployer = DeployAgent(backend_model=state.get("deploy_model", "qwen3.5-27b"))
    res = await deployer.analyze_requirement(state["user_query"])
    return {"lab_name": res["lab_name"]}

async def execute_deploy_node(state: DeployState):
    """
    节点2：物理部署拓扑，并收集简化的 netenv_info
    """
    lab_name = state["lab_name"]
    os.environ["LAB_NAME"] = lab_name # 设置环境变量以供 Klonet 等底层框架读取
    
    print(f"\n[System] 🛠️ 开始部署网络拓扑脚本: {lab_name}.py ...")
    
    # 假设所有拓扑脚本均存放在 src/net_env 目录下
    cwd = os.path.abspath(os.path.join(src_dir, "net_env"))
    cmd = ["uv", "run", f"{lab_name}.py"]
    
    try:
        # 执行脚本部署拓扑
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"拓扑部署失败，执行脚本出错:\n{result.stderr}"
            print(f"[Error] ❌ {error_msg}")
            return {
                "deploy_status": "Fatal",
                "netenv_info": f"部署失败: {error_msg}"
            }
            
        print(f"[System] ✅ 脚本 {lab_name}.py 执行完成！拓扑成功部署")
        time.sleep(4)
        
        # 部署成功后，通过 KlonetBaseAPI 获取全量拓扑信息
        print(f"[System] 📡 正在通过 Klonet API 抓取 '{lab_name}' 的全量拓扑结构...")
        api = KlonetBaseAPI(lab_name)
        raw_topo_dict = api.get_topo_json() 
        
        # 将数十 KB 的无用 JSON 数据精简为几十行 LLM 友好的纯文本
        netenv_info = simplify_topo(lab_name, raw_topo_dict)
        
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
    组装部署工作流
    START -> analyze_node (大模型决策) -> execute_deploy_node (执行与提取) -> END
    """
    workflow = StateGraph(DeployState)
    
    # 添加节点
    workflow.add_node("analyze_node", analyze_node)
    workflow.add_node("execute_deploy_node", execute_deploy_node)
    
    # 构建有向边
    workflow.add_edge(START, "analyze_node")
    workflow.add_edge("analyze_node", "execute_deploy_node")
    workflow.add_edge("execute_deploy_node", END)
    
    return workflow.compile()

# ==========================================
# 4. 本地测试入口
# ==========================================
if __name__ == "__main__":
    async def test():
        # 1. 初始化编译图
        graph = build_deploy_graph()
        
        # 2. 模拟外部输入 (假设后续 Agent 想要一个基于 OSPF 的网络)
        initial_state = {
            "user_query": "我们需要一个结构稍微复杂一点的企业级网络，最好能跑 OSPF 协议，以此来验证邻居异常的故障。",
            "deploy_model": "qwen3.5-27b",
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