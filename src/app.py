import os
import sys
import json
import time
import uuid
import re
import asyncio
import threading
import traceback
from datetime import datetime
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uvicorn

# ==========================================
# 1. 解决环境路径与真实 Agent 模块导包
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
agent_dir = os.path.join(current_dir, "agent")

if current_dir not in sys.path: sys.path.insert(0, current_dir)
if agent_dir not in sys.path: sys.path.insert(0, agent_dir)

from mcp_server.klonet_base_api import KlonetBaseAPI
from network_deploy_agent import build_deploy_graph 
from fault_inject_agent import build_inject_graph
from diagnose_agent import diagnose_fault
from judge_agent import build_judge_graph

def reset_topology(lab_name: str):
    print(f"\n**[System] 🧹 正在销毁网络拓扑 ({lab_name})...**")
    try:
        api = KlonetBaseAPI(lab_name)
        api.lab.reset_project()
        print(" **[System] ✅ 拓扑销毁成功。** ")
    except Exception as e:
        print(f" **[Error] ❌ 拓扑销毁失败: {e}** ")

# ==========================================
# 2. WebSocket 管理器与日志持久化拦截器
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conv_id: str):
        await websocket.accept()
        if conv_id not in self.active_connections:
            self.active_connections[conv_id] = []
        self.active_connections[conv_id].append(websocket)

    def disconnect(self, websocket: WebSocket, conv_id: str):
        if conv_id in self.active_connections and websocket in self.active_connections[conv_id]:
            self.active_connections[conv_id].remove(websocket)

    async def broadcast(self, message: str, conv_id: str):
        if conv_id in self.active_connections:
            for connection in self.active_connections[conv_id]:
                try: await connection.send_text(message)
                except: pass

manager = ConnectionManager()
active_conv_id = None  
fastapi_loop = None    
conversations = {}
CONVERSATIONS_FILE = 'conversations.json'

def save_conversations():
    try:
        with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except: pass

class AsyncOutputInterceptor:
    """
    终端输出拦截器：不仅推流，更负责将终端内容写入 JSON 历史！
    """
    def __init__(self, orig_stream):
        self.orig = orig_stream
        self.lock = threading.Lock()
        self.last_save = time.time()

    def __getattr__(self, item):
        return getattr(self.orig, item)

    def write(self, text):
        with self.lock:
            # 1. 打印到真实控制台
            try:
                self.orig.write(text)
                self.orig.flush()
            except: pass
            
            # 2. 持久化到 JSON 会话中，并跨线程推流
            global active_conv_id, fastapi_loop, conversations
            if active_conv_id and active_conv_id in conversations:
                clean_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
                if clean_text:
                    conv = conversations[active_conv_id]
                    # 💡 【核心修复】：所有的终端日志统一追加到当前激活的最后一个 Assistant 气泡中
                    if not conv['messages'] or conv['messages'][-1]['role'] != 'assistant':
                        conv['messages'].append({"role": "assistant", "content": clean_text})
                    else:
                        conv['messages'][-1]['content'] += clean_text
                    
                    # 防抖动保存（每 1 秒保存一次硬盘，防止高并发炸机）
                    if time.time() - self.last_save > 1.0:
                        save_conversations()
                        self.last_save = time.time()
                    
                    if fastapi_loop and not fastapi_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            manager.broadcast(json.dumps({"type": "stream", "content": clean_text}), active_conv_id),
                            fastapi_loop
                        )

    def flush(self):
        try: self.orig.flush()
        except: pass

# 激活拦截器
global_stdout = AsyncOutputInterceptor(sys.stdout)
sys.stdout = global_stdout

# ==========================================
# 3. FastAPI 生命周期配置
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global fastapi_loop, conversations
    fastapi_loop = asyncio.get_running_loop()
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
        except: pass
    yield
    save_conversations()

app = FastAPI(title="Nika Agent Web UI", lifespan=lifespan)

# ==========================================
# 4. 核心：四大状态机后台处理逻辑
# ==========================================

# 阶段一：网络拓扑部署
async def async_run_deploy(conv_id: str, user_query: str):
    conv = conversations[conv_id]
    try:
        print(f"\n **[System] 开始处理网络场景部署需求: {user_query}**")
        deploy_graph = build_deploy_graph()
        deploy_state = await deploy_graph.ainvoke({
            "user_query": user_query, 
            "deploy_model": "qwen3.5-27b", 
            "lab_name": "", 
            "deploy_status": "", 
            "netenv_info": ""
        })
        
        conv['context']['lab_name'] = deploy_state.get("lab_name", "unknown")
        conv['context']['netenv_info'] = deploy_state.get("netenv_info", "")
        
        conv['state'] = 'AWAITING_INJECT'
        # 💡 【核心修复】：不再调用额外的 push_message 创建新气泡，直接 print。
        # 拦截器会把它完美融进上方的长文本里！
        print("\n\n **🚥 [HIL] 拓扑部署已完毕。请选择下一步:** \n  - 输入 'r' 销毁当前拓扑并重新部署\n  - 直接输入【故障注入需求】(例如：注入主机接口DOWN故障) 进入注入阶段 ")
    except Exception as e:
        print(f"\n **❌ [System] 部署过程发生致命异常\n**错误信息**:\n```text\n{e}\n```**\n")
        conv['state'] = 'AWAITING_DEPLOY'
        print("\n\n **⚠️ [HIL] 部署失败，请检查控制台报错并重新输入部署需求。**")

# 阶段二：故障注入
async def async_run_inject(conv_id: str, fault_query: str):
    conv = conversations[conv_id]
    try:
        lab_name = conv['context']['lab_name']
        netenv_info = conv['context']['netenv_info']
        print(f" \n **💉 [System] 正在场景 {lab_name} 中注入故障: {fault_query}** ")
        
        inject_graph = build_inject_graph()
        inject_state = await inject_graph.ainvoke({
            "lab_name": lab_name,
            "netenv_info": netenv_info,
            "fault_query": fault_query,
            "actor_model": "qwen3.5-27b", 
            "max_steps": 50
        })
        
        conv['context']['problem_info'] = inject_state.get("problem_info", "未知现象")
        conv['context']['expected_fault'] = inject_state.get("expected_fault", "unknown")
        conv['context']['expected_location'] = inject_state.get("expected_location", "unknown")
        
        conv['state'] = 'AWAITING_DIAGNOSE'
        print("\n\n **🚥[HIL] 故障注入已完毕。请选择下一步:** \n  - 输入 'r' 重新进行故障注入\n  - 输入 'd' 或 '诊断' 进入下一步开始诊断 ")
    except Exception as e:
        print(f"\n **❌ [System] 部署过程发生致命异常\n**错误信息**:\n```text\n{e}\n```**\n")
        conv['state'] = 'AWAITING_INJECT'
        print("\n\n **⚠️ [HIL] 注入失败。请直接输入新的【故障注入需求】：**")

# 阶段三：故障诊断
async def async_run_diagnose(conv_id: str):
    conv = conversations[conv_id]
    ctx = conv['context']
    try:
        print(f"\n **🕵️‍♂️ [System] 正在启动高级网络故障诊断引擎...** ")
        diag_result = await diagnose_fault(
            lab_name=ctx["lab_name"],
            netenv_info=ctx["netenv_info"],
            problem_info=ctx["problem_info"],
            expected_fault=ctx["expected_fault"],
            expected_location=ctx["expected_location"],
            backend_model="qwen3.5-27b", 
            max_steps=50,
            time_limit=1200.0
        )
        
        ctx['diag_result'] = diag_result
        conv['state'] = 'AWAITING_EVAL'
        print("\n\n **🚥 [HIL] 故障诊断已完毕。请选择下一步:** \n  - 输入 'r' 或 '重新诊断' 打回重做\n  - 输入 'e' 或 '测评' 开始打分及全流程综合评测： ")
    except Exception as e:
        print(f"\n **❌ [System] 部署过程发生致命异常\n**错误信息**:\n```text\n{e}\n```**\n")
        conv['state'] = 'AWAITING_DIAGNOSE'
        print("\n\n **⚠️ [HIL] 诊断异常退出。请输入 'r' 重试或 'd' 再次诊断。**")

# 阶段四：测评与收尾生命周期
async def async_run_eval(conv_id: str):
    conv = conversations[conv_id]
    ctx = conv['context']
    dr = ctx['diag_result']
    try:
        print(f"\n**⚖️ [System] 正在启动终极裁判 (Judge Agent) 测评诊断全过程...** ")
        judge_graph = build_judge_graph()
        judge_state = await judge_graph.ainvoke({
            "netenv_info": ctx["netenv_info"],
            "problem_info": ctx["problem_info"],
            "expected_fault": ctx["expected_fault"],
            "expected_location": ctx["expected_location"],
            "diagnosis_result": dr["diagnosis_result"],
            "fault_location": dr["fault_location"],
            "location_correct": dr["location_correct"],
            "attribution_correct": dr["attribution_correct"],
            "tool_call_count": dr["tool_call_count"],
            "execution_time": dr["execution_time"],
            "token_usage": dr["token_usage"],
            "trajectory": dr["full_trajectory"], 
            "judge_model": "qwen3.5-27b" 
        })

        # 【核心修改】利用 Markdown 语法生成严谨的评价指标表格
        md_table = f"""
 🏆 [Judge] 最终综合评测报告

| 评测维度 | 结果 / 指标 |
| :--- | :--- |
| **期望故障位置** | `{ctx.get('expected_location', 'unknown')}` |
| **实际诊断位置** | `{dr.get('fault_location', 'unknown')}` |
| **位置准确性** | {'✅ 正确' if dr.get('location_correct') else '❌ 错误'} |
| **期望故障根因** | `{ctx.get('expected_fault', 'unknown')}` |
| **实际诊断根因** | `{dr.get('diagnosis_result', 'unknown')}` |
| **归因准确性** | {'✅ 正确' if dr.get('attribution_correct') else '❌ 错误'} |
| **工具调用次数** | **{dr.get('tool_call_count', 0)}** 次 |
| **执行耗时** | **{dr.get('execution_time', 0):.2f}** 秒 |
| **Token 总消耗** | **{dr.get('token_usage', {}).get('total_tokens', 0)}** Tokens |
| **🌟 综合评测总分**| **{judge_state.get('综合_score', 'N/A')} / 100** |

 📝 详细评价理由
{judge_state.get('subjective_reasoning', '无评语')}
"""
        print(md_table)
        
        if ctx.get("lab_name"):
            reset_topology(ctx["lab_name"])

        conv['state'] = 'DONE'
        print("\n\n **✅ [HIL] 全流程已圆满结束\n底层网络资源已释放清理，该对话窗口已永久锁定。若要进行下一次测试，请开启【新对话】。**")
    except Exception as e:
        print(f"\n **❌ [System] 测评过程发生致命异常\n```text\n{e}\n{traceback.format_exc()}\n```\n**")
        conv['state'] = 'AWAITING_EVAL'
        print("\n\n **⚠️ [HIL] 测评异常。请输入 'e' 再次尝试测评。**")

def worker_thread(coro_func, conv_id: str, *args):
    global active_conv_id
    active_conv_id = conv_id
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(coro_func(conv_id, *args))
    except Exception as e:
        print(f"后台线程异常: {e}")
    finally:
        active_conv_id = None
        loop.close()
        save_conversations() # 确保最终阶段落地
        if fastapi_loop and not fastapi_loop.is_closed():
            # 任务结束，下发 done 解除锁定状态
            asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)

# ==========================================
# 5. REST API: 分发和调度状态机
# ==========================================
class MessageReq(BaseModel):
    content: str

@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    response = HTMLResponse(content=html)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/api/conversations")
async def get_conversations():
    conv_list = [
        {'id': k, 'title': v.get('title', "新对话"), 'state': v.get('state', 'AWAITING_DEPLOY'), 'updated_at': v.get('updated_at', '')}
        for k, v in conversations.items()
    ]
    conv_list.sort(key=lambda x: x['updated_at'], reverse=True) 
    return conv_list

@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = conversations.get(conv_id, {})
    if 'messages' not in conv: conv['messages'] = []
    # 强制清理 isTyping 标志位，确保历史记录静态渲染不闪烁
    for m in conv['messages']:
        if 'isTyping' in m: m['isTyping'] = False
    return conv

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if conv_id in conversations:
        lab = conversations[conv_id].get('context', {}).get('lab_name', '')
        if lab and lab != "unknown" and conversations[conv_id].get('state') != 'DONE':
            try: reset_topology(lab) 
            except: pass
            
        del conversations[conv_id]
        save_conversations()
        return {'status': 'success'}
    return {'error': 'Not found'}

@app.post("/api/conversations")
async def create_conversation():
    conv_id = str(uuid.uuid4())
    conversations[conv_id] = {
        'id': conv_id, 
        'title': "新对话", 
        'state': 'AWAITING_DEPLOY',
        'context': {},
        'updated_at': datetime.now().isoformat(), 
        'messages': [
            {
                "role": "assistant", 
                # 【修改点】：添加空格，并使用双换行符 \n\n 隔离标题与正文，符合 Markdown 标准
                "content": "**[HIL] 👉 [阶段 1/4 - 部署] 请输入要部署的网络场景（例如：我需要一个静态路由网络）：**"
            }
        ]
    }
    save_conversations()
    return {'conversation_id': conv_id}

@app.post("/api/conversations/{conv_id}/chat")
async def process_chat(conv_id: str, req: MessageReq):
    if conv_id not in conversations:
        return {'error': 'Not found'}
        
    conv = conversations[conv_id]
    user_text = req.content.strip()
    
    conv['messages'].append({"role": "user", "content": user_text})
    if len(conv['messages']) <= 2:
        conv['title'] = user_text[:15] + "..."
    conv['updated_at'] = datetime.now().isoformat()
    save_conversations()
    
    state = conv.get('state', 'AWAITING_DEPLOY')
    
    if state == 'AWAITING_DEPLOY':
        threading.Thread(target=worker_thread, args=(async_run_deploy, conv_id, user_text)).start()
        
    elif state == 'AWAITING_INJECT':
        if user_text.lower() in ['r', '重新部署']:
            lab = conv['context'].get('lab_name', '')
            if lab: reset_topology(lab)
            conv['state'] = 'AWAITING_DEPLOY'
           
            active_conv_id_temp = conv_id  # 打印 HIL 路由日志
            conv['messages'].append({"role": "assistant", "content": "\n [System] 拓扑已销毁。\n\n **[HIL] 👉 请重新输入您要部署的网络场景：**"})
            save_conversations()
            if fastapi_loop: asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)
        else:
            threading.Thread(target=worker_thread, args=(async_run_inject, conv_id, user_text)).start()
            
    elif state == 'AWAITING_DIAGNOSE':
        if user_text.lower() in ['r', '重新注入']:
            conv['state'] = 'AWAITING_INJECT'
            conv['messages'].append({"role": "assistant", "content": "\n **[HIL] 👉 请重新输入新的【故障注入需求】：**"})
            save_conversations()
            if fastapi_loop: asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)
        elif user_text.lower() in ['d', '诊断']:
            threading.Thread(target=worker_thread, args=(async_run_diagnose, conv_id)).start()
        else:
            conv['messages'].append({"role": "assistant", "content": "\n **[HIL] ⚠️ 输入无效。请输入 'r' 重新注入，或输入 'd' 开始诊断。**"})
            save_conversations()
            if fastapi_loop: asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)
            
    elif state == 'AWAITING_EVAL':
        if user_text.lower() in ['r', '重新诊断']:
            threading.Thread(target=worker_thread, args=(async_run_diagnose, conv_id)).start()
        elif user_text.lower() in ['e', '测评', '评测']:
            threading.Thread(target=worker_thread, args=(async_run_eval, conv_id)).start()
        else:
            conv['messages'].append({"role": "assistant", "content": "\n **[HIL] ⚠️ 输入无效。请输入 'r' 重新诊断，或输入 'e' 开始综合测评。**"})
            save_conversations()
            if fastapi_loop: asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)
            
    elif state == 'DONE':
        conv['messages'].append({"role": "assistant", "content": "\n **[HIL] ⚠️ 当前对话全流程已经结束。若要测试，请开启【新对话】。**"})
        save_conversations()
        if fastapi_loop: asyncio.run_coroutine_threadsafe(manager.broadcast(json.dumps({"type": "done"}), conv_id), fastapi_loop)

    return {'status': 'processing'}

@app.websocket("/ws/{conv_id}")
async def websocket_endpoint(websocket: WebSocket, conv_id: str):
    await manager.connect(websocket, conv_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, conv_id)

if __name__ == "__main__":
    print("🚀 Nika Web Server (四大 Agent 集成) is running at http://127.0.0.1:8080")
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True)