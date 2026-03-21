# 导入系统与环境相关模块
import os
# 设置本地环回代理环境变量，防止某些网络环境下请求被拦截或超时
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

# 导入 Flask Web 框架与 SocketIO 实时通信模块
# 【修改处 1】：在导入列表中追加 make_response 工具
from flask import Flask, request, jsonify, make_response
from flask_socketio import SocketIO
# 导入常用的工具模块：JSON处理、UUID生成、时间、多线程、系统与异步
import json
import uuid
import time
import threading
import sys
import asyncio
import logging
import re
from queue import Queue
from datetime import datetime
import traceback

# ==========================================
# 解决环境路径与导包报错
# ==========================================
# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目的根目录路径（上一级目录）
project_root = os.path.abspath(os.path.join(current_dir, ".."))
# 如果当前目录不在系统路径中，则优先插入，确保自定义包能被找到
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 尝试导入核心诊断引擎 Orchestrator
try:
    from orchestrator import Orchestrator
    # 实例化全局引擎对象
    global_orchestrator = Orchestrator()
    print(">>> 成功加载 Orchestrator 核心模块！")
except ImportError as e:
    # 导入失败不抛出致命异常，打印警告并让系统依然能够纯前端启动运行
    print(f">>> 警告: 无法加载 orchestrator.py，错误信息: {e}")
    global_orchestrator = None

# 初始化 Flask 应用
app = Flask(__name__)
# 配置应用的 Secret Key
app.config['SECRET_KEY'] = 'your-secret-key'
# 初始化 SocketIO，允许跨域，使用多线程异步模式
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 关闭 werkzeug 的默认 HTTP 访问日志，保持控制台清爽
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# 全局内存变量声明
conversations = {}          # 存储所有对话历史的字典字典
output_queue = Queue()      # 用于向前端网页推送标准输出的线程安全队列
active_conv_id = None       # 当前正在前台活跃执行任务的对话 ID
CONVERSATIONS_FILE = 'conversations.json' # 本地持久化保存历史记录的文件名

# ==========================================
# 🌟 终极解决方案：同时接管 Web 输出、System.log 和 Case.log 的拦截器！
# ==========================================
class UnifiedOutputInterceptor:
    # 拦截器初始化
    def __init__(self, orig_stream):
        self.orig = orig_stream # 保存原始的系统标准输出（控制台）
        self.lock = threading.Lock() # 多线程锁，防止并发写入日志打架
        
        # 准备全局 System.log 日志保存路径
        self.sys_log_path = os.path.join(project_root, "runtime", "system.log")
        os.makedirs(os.path.dirname(self.sys_log_path), exist_ok=True) # 确保存储目录存在
        
        self.case_log_file = None # 预留具体案例独立日志的文件句柄

    # 前端点击执行时，动态开辟一个当前 case 的独立日志文件
    def start_case_log(self, lab_name, fault_name):
        with self.lock:
            if self.case_log_file:
                # 如果上一个还在开着，先尝试安全关闭它
                try: self.case_log_file.close()
                except: pass
            # 创建并进入 cases 日志专属目录
            case_dir = os.path.join(project_root, "runtime", "cases")
            os.makedirs(case_dir, exist_ok=True)
            # 根据场景和故障命名，以追加模式打开文件
            path = os.path.join(case_dir, f"{lab_name}_{fault_name}.log")
            self.case_log_file = open(path, "a", encoding="utf-8")

    # 执行结束时安全关闭该独立文件
    def stop_case_log(self):
        with self.lock:
            if self.case_log_file:
                try: self.case_log_file.close()
                except: pass
                self.case_log_file = None

    # 重写写入核心方法
    def write(self, text):
        with self.lock:
            # 1. 打印到原始终端控制台
            try:
                self.orig.write(text)
                self.orig.flush()
            except: pass
            
            # 2. 同步写入两个本地日志文件
            try:
                if isinstance(text, str):
                    # 追加到系统级别日志 runtime/system.log
                    with open(self.sys_log_path, "a", encoding="utf-8") as f:
                        f.write(text)
                    # 同步追加到当前运行时独立生成的案例日志里
                    if self.case_log_file:
                        self.case_log_file.write(text)
                        self.case_log_file.flush()
            except: pass
            
            # 3. 将输出流压入推送队列，发给前端网页
            try:
                global active_conv_id
                # 只有当正在执行任务，且文本不为空时才处理
                if active_conv_id and isinstance(text, str) and text:
                    # 使用正则过滤掉控制台颜色转义符，以免在前端乱码
                    clean_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
                    if clean_text:
                        # 放入队列等待 output_monitor 线程提走发送
                        output_queue.put(('output', clean_text, active_conv_id))
            except: pass

    # 冲刷缓冲区方法映射
    def flush(self):
        try: self.orig.flush()
        except: pass

# 拦截系统原生 print 并将其劫持到我们自定义的类上
global_stdout = UnifiedOutputInterceptor(sys.stdout)
sys.stdout = global_stdout


# ==========================================
# 前端 HTML/CSS/JS 原生模板 (修改版)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PlayGround Network Diagnosis</title>
    <script src="https://cdn.bootcdn.net/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
    <style>
        /* === 根节点颜色变量定义，方便全局统一调整 UI 主题 === */
        :root {
            --border-light: #e0e0e0; 
            --border-medium: #cccccc;
            --border-dark: #999999;  
            --bg-color: #ffffff;     
            --bg-hover: #f5f5f5;     
            --bg-chat-user: #000000; 
            --text-user: #ffffff;    
            --bg-chat-ai: #f9f9f9;   
            --text-main: #000000;    
            --text-muted: #666666;   
        }
        
        /* 全局重置边距和包围盒计算方式 */
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        /* body: 采用 Flex 左右布局，禁止浏览器本身的滚动条，限制屏幕高度 */
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: var(--bg-color); color: var(--text-main); height: 100vh; display: flex; overflow: hidden; }
        
        /* === 左区 (对话历史侧边栏) === */
        #left-zone { width: 240px; height: 100%; border-right: 1px solid var(--border-medium); display: flex; flex-direction: column; background: #fff; flex-shrink: 0; }
        #left-zone h3 { text-align: center; padding: 15px 0; font-size: 16px; border-bottom: 1px solid var(--border-light); font-weight: normal; }
        
        /* 新建对话按钮 */
        #new-chat-btn { margin: 10px; padding: 8px; background: #000; color: #fff; text-align: center; cursor: pointer; border: 1px solid #000; font-size: 14px; transition: 0.2s; }
        #new-chat-btn:hover { background: #333; }
        
        /* 历史列表滚动区域 */
        #history-list { flex: 1; overflow-y: auto; list-style: none; padding: 0; }
        .history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; border-bottom: 1px solid var(--border-light); cursor: pointer; font-size: 12px; color: var(--text-muted); transition: background 0.2s; }
        .history-item:hover, .history-item.active { background: var(--bg-hover); color: var(--text-main); }
        .history-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .delete-btn { font-size: 14px; padding: 2px 6px; border-radius: 4px; cursor: pointer; opacity: 0.5; transition: 0.2s; }
        .delete-btn:hover { opacity: 1; background: #ffe6e6; color: #d00; }
        
        /* === 右侧大区 === */
        #right-container { flex: 1; display: flex; flex-direction: column; height: 100%; min-width: 0; }
        
        /* 右上区 (Top Bar) */
        #top-right-zone { height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid var(--border-medium); flex-shrink: 0; }
        .logo { font-size: 28px; font-weight: bold; letter-spacing: -0.5px; }
        .session-title { font-size: 16px; color: var(--text-muted); text-align: center; flex: 1; font-weight: 600;}
        
        /* === 中间区 (聊天日志面板) === */
        #middle-zone { flex: 1; overflow-y: auto; padding: 20px; background: #fafafa; display: flex; flex-direction: column; gap: 15px; border-bottom: 1px solid var(--border-medium); }
        
        /* 聊天气泡包裹容器 */
        .msg-row { display: flex; width: 100%; align-items: flex-start; gap: 10px; }
        .row-user { justify-content: flex-end; }  
        .row-ai { justify-content: flex-start; }  
        
        /* 角色头像 */
        .msg-avatar { font-size: 13px; font-weight: bold; color: #555; white-space: nowrap; padding-top: 10px; user-select: none; }
        
        /* 气泡基础样式：允许断词，保留换行符 */
        .message { padding: 12px 16px; border-radius: 4px; font-size: 14px; line-height: 1.6; word-wrap: break-word; white-space: pre-wrap;}
        
        /* 用户气泡样式 */
        .msg-user { background: var(--bg-chat-user); color: var(--text-user); max-width: 75%; }
        
        /* AI 气泡样式（终端感） */
        .msg-ai { background: var(--bg-chat-ai); border: 1px solid var(--border-light); color: var(--text-main); font-family: Consolas, monospace; width: 90%; max-width: 90%; }
        
        /* 系统消息气泡 */
        .msg-sys { align-self: flex-start; background: transparent; color: var(--text-muted); font-size: 12px; border: 1px dashed var(--border-light); margin-left: 75px; }
        
        /* === 底部大区 (控制台总容器) === */
        /* 固定 320px 高度 */
        #bottom-container { height: 320px; display: flex; flex-shrink: 0; background: #fff; }
        
        /* ==================== 区域宽度分配调整区 ==================== */
        /* 【恢复要求比例 5:7】左区占 5 */
        #bottom-zone { flex: 5; display: flex; flex-direction: column; border-right: 1px solid var(--border-medium); padding: 15px; }
        
        /* 【恢复要求比例 5:7】右区占 7 */
        #bottom-right-zone { flex: 7; padding: 15px; display: flex; flex-direction: column; min-width: 0; }
        /* ========================================================= */

        .section-title { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;}

        /* ==================== 底部左区：场景区竖排调整 ==================== */
        /* 场景按钮网格：限制高度、可【竖向】滚动、展示 3x2=6 个 */
        #scenarios-grid { 
            display: grid; 
            grid-template-columns: repeat(3, 1fr); /* 强制 3 列 */
            /* 【精细计算高度】确保刚好完美显示 2 行按钮，第 3 行开始隐藏需要竖向滚动。
               (100%容器高度减去1个8px间距) / 2 = 单个按钮高度 */
            grid-auto-rows: calc((100% - 8px) / 2); 
            gap: 8px; 
            overflow-y: auto;   /* 【要求修改】允许竖向滑动 */
            overflow-x: hidden; /* 绝对禁止横向滑动 */
            flex: 1;            /* 撑满剩余高度 */
            padding-right: 4px; /* 给右侧竖向滚动条留出一点边距防止贴文字太紧 */
        }
        
        /* 场景区专用【竖向】滚动条美化 */
        #scenarios-grid::-webkit-scrollbar { width: 6px; }
        #scenarios-grid::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
        #scenarios-grid::-webkit-scrollbar-thumb { background: #bbb; border-radius: 4px; }
        #scenarios-grid::-webkit-scrollbar-thumb:hover { background: #888; }
        /* ============================================================== */

        /* ==================== 底部左区：输入区布局及实线分割 ==================== */
        .input-area { 
            display: flex; 
            gap: 10px; 
            height: 100px; /* 【恢复原始固定高度 80px】，使其与最开始的一模一样 */
            flex-shrink: 0; 
            
            /* 【实体隔断线核心实现】：使用和整体 UI(border-medium)一致的粗细与颜色 */
            border-top: 1px solid var(--border-medium); 
            
            /* 使用负边距 (Negative Margin) 抵消父元素 bottom-zone 的 padding 15px，
               强制让这条线上左右两端完全顶满父盒子的边缘，实现“完全隔断” */
            margin-left: -15px;  
            margin-right: -15px; 
            
            /* 内边距补回 15px，防止里面的输入框和按钮贴到边上 */
            padding-left: 15px;  
            padding-right: 15px; 
            padding-top: 15px;   
            margin-top: 15px;    
        }
        
        /* 用户输入的自然语言大文本框 */
        #user-input { flex: 1; resize: none; padding: 10px; border: 1px solid var(--border-dark); font-family: inherit; font-size: 14px; outline: none; }
        #user-input:focus { border-color: #000; }
        
        /* 执行按钮与步数输入的包裹垂直列：宽度定死 140px，按比例在 flex 下自动拉高 */
        .action-area { display: flex; flex-direction: column; width: 120px; gap: 6px; } 
        .action-area input { flex: 1; text-align: center; border: 1px solid var(--border-dark); font-size: 12px; outline: none; }
        .action-area input:focus { border-color: #000; }
        .action-area button { flex: 1; background: #000; color: #fff; border: none; cursor: pointer; font-size: 14px; transition: 0.2s; font-weight: bold;}
        .action-area button:hover { background: #333; }
        /* ============================================================== */
        
        /* === 底部右区 === */
        /* ==================== 底部右区：完美无截断动态按钮计算 ==================== */
        #faults-grid { 
            display: grid; 
            grid-template-rows: repeat(4, 1fr); /* 保持 4 行 */
            
            /* 【核心难点解决】：不要写死 160px！
               根据屏幕及父容器宽度动态等分计算：容器 100% 宽度，减去 3 个 8px 的缝隙(24px)后，
               精准除以 4。这样在任何显示器下，首屏都能完美丝毫不差地容纳 4x4=16 个按钮的完整边框！*/
            grid-auto-columns: calc((100% - 24px) / 4); 
            
            grid-auto-flow: column;             
            gap: 8px; 
            overflow-x: auto;                   
            overflow-y: hidden;                 
            flex: 1; 
            padding-bottom: 8px; 

            /* 【修改处 3】：增加 2 像素的右侧内边距，专门为滑动到最右端时的按钮边框留出空间，防止被父容器裁切“吞掉” */
            padding-right: 2px;               
        }
        
        /* 故障区滚动条美化 */
        #faults-grid::-webkit-scrollbar { height: 8px; }
        #faults-grid::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
        #faults-grid::-webkit-scrollbar-thumb { background: #bbb; border-radius: 4px; }
        #faults-grid::-webkit-scrollbar-thumb:hover { background: #888; }
        
        /* 通用按钮基础内部图文排版样式 */
        .btn { border: 1px solid var(--border-medium); background: #fff; color: #000; cursor: pointer; padding: 4px; text-align: center; display: flex; align-items: center; justify-content: center; flex-direction: column; transition: 0.1s; line-height: 1.2;}
        .btn span.en { font-weight: bold; margin-bottom: 2px; font-size: 12px;}  
        .btn span.cn { font-size: 11px; color: #555; margin-bottom: 2px;}        
        .btn span.topo { font-size: 10px; color: #1a73e8; font-weight: bold;}    
        .btn:hover { border-color: #000; background: #f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
        
        /* 运行任务时的页面全局冻结遮罩特效 */
        .readonly-overlay { pointer-events: none; opacity: 0.5; filter: grayscale(100%); }
    </style>
</head>
<body>
    <div id="left-zone">
        <h3>对话历史</h3>
        <div id="new-chat-btn">+ 新建对话</div>
        <ul id="history-list"></ul>
    </div>
    <div id="right-container">
        <div id="top-right-zone">
            <div class="logo">PlayGround</div>
            <div class="session-title" id="session-title">准备就绪</div>
            <div style="width: 100px;"></div> 
        </div>
        <div id="middle-zone">
            <div class="message msg-sys">系统已就绪。请从下方选择场景与故障以发起测试任务。</div>
        </div>
        <div id="bottom-container">
            <div id="bottom-zone">
                <div class="section-title">网络场景 (Scenarios - 7种) <span style="font-weight:normal;color:#1a73e8;">← 鼠标放此竖向拖动查看全部 →</span></div>
                <div id="scenarios-grid"></div>
                <div class="input-area">
                    <textarea id="user-input" placeholder="输入自然语言(暂未接入Agent对话功能)，或点击右侧执行..."></textarea>
                    <div class="action-area">
                        <input type="number" id="max-steps-input" placeholder="Agent尝试次数" value="50" title="Agent 最大尝试次数">
                        <button id="send-btn">执行</button>
                    </div>
                </div>
            </div>
            <div id="bottom-right-zone">
                <div class="section-title">故障注入选区 (Faults - 28种) <span style="font-weight:normal;color:#1a73e8;">← 鼠标放此横向拖动查看全部 →</span></div>
                <div id="faults-grid"></div>
            </div>
        </div>
    </div>

<script>
    // 实例化 WebSocket 连接
    const socket = io();
    let currentConvId = null; // 当前会话唯一 ID
    let labName = null;       // 选中的实验环境名称
    let faultName = null;     // 选中的故障名称
    let isReadOnly = false;   // 前端是否被锁定的状态标识
    let frozenTitle = null;   // 执行任务时冻结的时间戳标题

    // ==================== 数据：7 大网络场景 (增加 ai_reasoning) ====================
    const scenarios = [
        { id: "static_routing", name: "静态路由" }, { id: "simple_bgp", name: "简单 BGP" },
        { id: "ospf_enterprise", name: "OSPF 企业网" }, { id: "rip_internet", name: "RIP 小型网络" },
        { id: "sdn_openflow", name: "SDN 网络" }, { id: "p4_star", name: "P4 星型网络" },
        { id: "ai_reasoning", name: "AI推理" } // 【新增的第 7 个场景】
    ];

    // 故障库常量定义字典
    const faults = [
        { id: "ip_misconfig", name: "IP配置错误", best_topo: "static_routing" }, 
        { id: "default_route_missing", name: "缺默认路由", best_topo: "static_routing" },
        { id: "arp_poisoning", name: "ARP投毒", best_topo: "static_routing" }, 
        { id: "interface_down", name: "接口DOWN", best_topo: "static_routing" },
        { id: "dns_error", name: "DNS错误", best_topo: "static_routing" }, 
        { id: "high_cpu_load", name: "CPU满载", best_topo: "static_routing" },
        { id: "route_missing", name: "路由丢失", best_topo: "static_routing" }, 
        { id: "static_route_blackhole", name: "黑洞路由", best_topo: "static_routing" },
        { id: "router_data_plane_drop", name: "数据面丢弃", best_topo: "static_routing" }, 
        { id: "bgp_neighbor_shutdown", name: "BGP邻居断", best_topo: "simple_bgp" },
        { id: "bgp_withdraw_route", name: "BGP路由撤销", best_topo: "simple_bgp" }, 
        { id: "bgp_wrong_peer_asn", name: "BGP AS错", best_topo: "simple_bgp" },
        { id: "ospf_passive_interface", name: "OSPF被动接口", best_topo: "ospf_enterprise" }, 
        { id: "ospf_cost_spike", name: "OSPF开销增", best_topo: "ospf_enterprise" },
        { id: "ospf_daemon_crash", name: "OSPF进程崩", best_topo: "ospf_enterprise" }, 
        { id: "rip_passive_interface", name: "RIP被动接口", best_topo: "rip_internet" },
        { id: "rip_route_filter", name: "RIP路由过滤", best_topo: "rip_internet" }, 
        { id: "rip_metric_offset", name: "RIP跳数篡改", best_topo: "rip_internet" },
        { id: "sdn_controller_crash", name: "SDN控制器崩", best_topo: "sdn_openflow" }, 
        { id: "ovs_disconnect_controller", name: "OVS断连", best_topo: "sdn_openflow" },
        { id: "ovs_global_drop_flow", name: "OVS全局丢弃", best_topo: "sdn_openflow" }, 
        { id: "bmv2_process_crash", name: "BMV2崩溃", best_topo: "p4_star" },
        { id: "p4_table_drop", name: "P4流表丢弃", best_topo: "p4_star" }, 
        { id: "p4_wrong_forwarding", name: "P4转发错", best_topo: "p4_star" },
        { id: "link_latency", name: "高延迟", best_topo: "simple_bgp" }, 
        { id: "link_loss", name: "丢包", best_topo: "simple_bgp" },
        { id: "link_jitter", name: "抖动", best_topo: "simple_bgp" }, 
        { id: "link_bandwidth", name: "带宽限制", best_topo: "simple_bgp" }
    ];

    // ==========================================
    // 🌟 修复后的打字机引擎 (Typewriter Engine)
    // ==========================================
    let currentAiBubble = null; // 当前正在活动的 AI 气泡对象节点
    let typeQueue = "";         // 字符缓存队列
    let isTyping = false;       // 打字机运行状态标识

    // 打字机核心递归推字函数
    function processTypeQueue() {
        if (typeQueue.length > 0 && currentAiBubble) {
            
            // 防止离开页面到后台导致 setTimeout 被浏览器限流卡死
            if (document.hidden) {
                // 如果用户当前切换去了别的页面标签卡（页面在后台），直接暴力将缓冲区剩下的字全扔上去
                currentAiBubble.innerText += typeQueue;
                typeQueue = ""; // 一次性清空队列
            } else {
                // 页面正常在前台：模拟黑客敲击键盘动画，逐字吐出
                currentAiBubble.innerText += typeQueue.charAt(0);
                // 摘掉队列首个字符
                typeQueue = typeQueue.substring(1);
            }
            
            // 实时控制滚动条追底
            const zone = document.getElementById('middle-zone');
            zone.scrollTop = zone.scrollHeight;
            
            // 队列没倒空，过 10 毫秒接着吐下一个字
            if (typeQueue.length > 0) {
                setTimeout(processTypeQueue, 10);
            } else {
                isTyping = false; // 吐干了，睡大觉
            }
        } else {
            isTyping = false;
        }
    }

    // UI 控制枢纽：向聊天区推送消息（分为新建行和追加流式模式）
    function appendMessage(sender, content, appendMode = false) {
        const zone = document.getElementById('middle-zone');
        
        // 【流式追加】：用于打字机接收后端零碎的 Agent 日志切片
        if (appendMode && currentAiBubble && sender === 'ai') {
            typeQueue += content; // 将后端的字塞入队列
            if (!isTyping) {      // 如果打字机休息了，重新激活它
                isTyping = true;
                processTypeQueue();
            }
            return;
        }
        
        // 【全新单行】：用于打印用户输入或者直接渲染历史记录
        typeQueue = ""; // 防止串台清空重置
        isTyping = false;
        
        const rowDiv = document.createElement('div');
        const bubbleDiv = document.createElement('div');
        bubbleDiv.innerText = content; // 直接完整赋值
        
        if (sender === 'user') {
            // 右侧用户 UI
            rowDiv.className = 'msg-row row-user';
            bubbleDiv.className = 'message msg-user';
            const avatar = document.createElement('div');
            avatar.className = 'msg-avatar';
            avatar.innerText = 'You 🧑‍💻'; 
            rowDiv.appendChild(bubbleDiv);
            rowDiv.appendChild(avatar); 
            currentAiBubble = null; // 中断 AI 打字目标
            zone.appendChild(rowDiv);
            
        } else if (sender === 'ai') {
            // 左侧 AI Agent UI
            rowDiv.className = 'msg-row row-ai';
            bubbleDiv.className = 'message msg-ai';
            const avatar = document.createElement('div');
            avatar.className = 'msg-avatar';
            avatar.innerText = '🤖 Agent'; 
            rowDiv.appendChild(avatar);    
            rowDiv.appendChild(bubbleDiv); 
            currentAiBubble = bubbleDiv; // 把这个新创建的框变成打字机接下来的目标宿主
            zone.appendChild(rowDiv);
            
        } else {
            // 系统居中提示 UI
            bubbleDiv.className = 'message msg-sys';
            currentAiBubble = null;
            zone.appendChild(bubbleDiv);
        }
        zone.scrollTop = zone.scrollHeight; // 压底
    }

    // ==========================================
    // 页面交互事件与动态渲染
    // ==========================================
    
    // 更新顶部标题指示栏
    function updateTitle() {
        if(frozenTitle) { document.getElementById('session-title').innerText = frozenTitle; return; }
        const now = new Date();
        const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
        const lName = labName ? labName : "待选场景";
        const fName = faultName ? faultName : "待选故障";
        document.getElementById('session-title').innerText = `${dateStr} | ${lName} | ${fName}`;
    }

    // 🌟 【要求修改】：完全填充补齐按钮与对话输入框的同步联动功能
    function updateInputBox() {
        const userInput = document.getElementById('user-input');
        
        // 如果目前是只读锁定模式（任务执行中或看历史），不再随意改动框内文字
        if (isReadOnly) return;
        
        // 按下场景或故障按钮后，动态生成友好的提示自然语言
        if (labName && faultName) {
            userInput.value = `请帮我诊断 ${labName} 场景下发生的 ${faultName} 故障问题。`;
        } else if (labName) {
            userInput.value = `已选定网络场景：${labName}，等待您选择故障类型...`;
        } else if (faultName) {
            userInput.value = `已选定故障类型：${faultName}，等待您选择网络场景...`;
        } else {
            userInput.value = "";
        }
    }

    // 生成底部的海量按钮
    function renderButtons() {
        // 渲染网络场景按钮
        const sGrid = document.getElementById('scenarios-grid');
        scenarios.forEach(s => {
            let b = document.createElement('button');
            b.className = 'btn';
            b.innerHTML = `<span class="en">${s.id}</span><span class="cn">${s.name}</span>`;
            b.onclick = () => { 
                labName = s.id; 
                appendMessage('sys', `>> 已选择网络场景: ${s.name} (${s.id})`);
                updateTitle(); 
                updateInputBox(); // 【触发联动更新输入框文字】
            };
            sGrid.appendChild(b);
        });

        // 渲染故障注入按钮
        const fGrid = document.getElementById('faults-grid');
        faults.forEach(f => {
            let b = document.createElement('button');
            b.className = 'btn';
            b.innerHTML = `<span class="en">${f.id}</span><span class="cn">${f.name}</span><span class="topo">${f.best_topo}</span>`;
            b.onclick = () => { 
                faultName = f.id; 
                appendMessage('sys', `>> 已选择注入故障: ${f.name} (${f.id})`);
                updateTitle(); 
                updateInputBox(); // 【触发联动更新输入框文字】
            };
            fGrid.appendChild(b);
        });
    }

    try { renderButtons(); } catch(e) {}

    // 执行或看历史时，锁定下面整个区域的输入与点击
    function setMode(readonly) {
        isReadOnly = readonly;
        document.getElementById('bottom-container').classList.toggle('readonly-overlay', readonly);
    }

    // 删除单条记录
    async function deleteConversation(id, event) {
        event.stopPropagation(); 
        if(!confirm("确定要删除这条诊断记录吗？")) return;
        try {
            await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
            if (currentConvId === id) newConversation(); // 如果删除的是正在看的，就刷白
            else loadHistoryList();
        } catch(e) { console.error(e); }
    }

    // 加载左侧列表
    async function loadHistoryList() {
        try {
            const res = await fetch('/api/conversations');
            const data = await res.json();
            const list = document.getElementById('history-list');
            list.innerHTML = '';
            data.forEach(c => {
                let li = document.createElement('li');
                li.className = 'history-item';
                li.innerHTML = `<span class="history-title">${c.title || c.id}</span><span class="delete-btn" onclick="deleteConversation('${c.id}', event)">✖</span>`;
                li.onclick = (e) => {
                    if(e.target.classList.contains('delete-btn')) return;
                    loadConversation(c.id); // 点击非删除区，进入该会话
                };
                list.appendChild(li);
            });
        } catch(e) {}
    }

    // 读取并渲染指定历史记录
    async function loadConversation(id) {
        currentConvId = id;
        try {
            const res = await fetch(`/api/conversations/${id}`);
            const data = await res.json();
            document.getElementById('middle-zone').innerHTML = ''; 
            currentAiBubble = null;
            // 批量渲染：不走打字机 appendMode=false
            if(data.messages) {
                data.messages.forEach(m => { appendMessage(m.type, m.content, false); });
            }
            frozenTitle = data.title; 
            updateTitle();
            setMode(true); // 看历史肯定是只读锁住状态
        } catch(e) {}
    }

    // 点击左侧上方按钮新建一张空白草稿对话
    async function newConversation() {
        try {
            currentConvId = null; // 幽灵态不分配后端ID
            document.getElementById('middle-zone').innerHTML = '<div class="message msg-sys">新测试已就绪。请先选择场景和故障，系统将在点击[执行]后自动生成历史记录。</div>';
            currentAiBubble = null;
            
            // 重置全部状态
            labName = null; 
            faultName = null; 
            frozenTitle = null;
            
            document.getElementById('user-input').value = ""; // 清空用户的对话框遗留文字
            
            setMode(false);   // 解除下面的半透明不可点击封印！
        } catch(e) { 
            console.error(e); 
        }
    }

    // 发起排障执行（自带防并发锁及延时平滑）
    async function triggerTask() {
        if (isReadOnly) return; 
        
        if (!labName || !faultName) {
            alert("请先点击按钮选择【网络场景】和【注入故障】！");
            return;
        }
        
        const maxSteps = parseInt(document.getElementById('max-steps-input').value) || 50;
        setMode(true); // 发起执行立刻封禁底部，防多点
        frozenTitle = document.getElementById('session-title').innerText; // 冻结时间
        
        // 渲染一次性输入
        const taskStr = `【执行排障任务】 场景: ${labName} | 故障: ${faultName} | 最大步数: ${maxSteps}`;
        appendMessage('user', taskStr);
        // 先塞一个准备给 AI 后续拼接用的空终端框头
        appendMessage('ai', `> [System] Orchestrator Agent 引擎启动...\n`, false);

        // 延迟一半秒发送正式请求，以展现顺滑的 UI 过渡
        setTimeout(async () => {
            try {
                // 如果是新创建刚点进来的空状态，则临时向后端注册一个新的 ID 落盘
                if (!currentConvId) {
                    const res = await fetch('/api/conversations', { method: 'POST' });
                    const data = await res.json();
                    currentConvId = data.conversation_id; 
                    if(socket) socket.emit('join_conversation', { conversation_id: currentConvId });
                }

                // 派发指令给 Flask 后端启动真正的 python 引擎线程
                await fetch(`/api/conversations/${currentConvId}/execute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        lab_name: labName, fault_name: faultName, max_steps: maxSteps, title: frozenTitle 
                    })
                });
                
                loadHistoryList(); // 左侧立刻刷出刚才生成的那条记录
                
            } catch (e) {
                console.error("执行任务失败:", e);
                appendMessage('sys', "【系统警告】后端请求失败，请检查控制台。");
                setMode(false); // 异常时回滚锁释放
            }
        }, 500); 
    }

    // 绑定各类按钮动作
    document.getElementById('send-btn').onclick = triggerTask;
    document.getElementById('new-chat-btn').onclick = newConversation;

    // WebSocket 接盘后端源源不断的数据：推入打字机缓冲池
    socket.on('orchestrator_output', data => {
        if (data.conv_id === currentConvId) {
            appendMessage('ai', data.content, true); // true 代表流式追加
        }
    });

    // 后端执行完发的结束广播指令
    socket.on('orchestrator_done', data => {
        if (data.conv_id === currentConvId) {
            appendMessage('ai', `\n> [任务执行结束] `, true);
            setMode(false);    // 自动解锁下方区域
            loadHistoryList(); // 左侧刷新修改时间
        }
    });

    // 初始化时加载历史并开启纯前端空白画布，并设定时间定时器
    try {
        loadHistoryList();
        newConversation(); 
        setInterval(updateTitle, 1000); 
    } catch(e) {}
</script>
</body>
</html>
"""

# ==========================================
# 后端业务逻辑与全局输出队列
# ==========================================
# 从本地 json 文件拉取对话状态
def load_conversations():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return {}

# 存储整个对话字典到本地 json
def save_conversations():
    try:
        with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 开在子线程里运行核心诊断任务的函数包装器
def run_orchestrator_task(conversation_id, lab_name, fault_name, max_steps):
    global active_conv_id
    active_conv_id = conversation_id
    
    # 🌟 启动记录该对话特定的 Case log 文件
    global_stdout.start_case_log(lab_name, fault_name)
    
    try:
        if global_orchestrator:
            # 隔离事件循环供异步任务跑
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(global_orchestrator.run_test(lab_name, fault_name, max_steps=max_steps))
            result = "排障工作流执行完毕。"
        else:
            # 没有包则虚拟跑个占位模拟任务
            result = "未检测到 Orchestrator 模块，直接结束。"
            time.sleep(2)
    except Exception as e:
        # 万一引擎炸了，抓取 Traceback 在终端报错
        error_msg = f"Orchestrator 致命错误: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        result = f"异常中断: {str(e)}"
    finally:
        active_conv_id = None
        # 🌟 必须保证 Case 日志文件在使用完毕后关闭
        global_stdout.stop_case_log()
        # 通知前端：这波活干完了
        socketio.emit('orchestrator_done', {'result': result, 'conv_id': conversation_id})

# 常驻后台队列分发小妹：把拦截到的全局控制台文本向前端分片 WebSocket 广播
def output_monitor():
    last_save_time = time.time()
    while True:
        try:
            needs_save = False
            while not output_queue.empty():
                msg_type, content, conv_id = output_queue.get()
                
                # 如果这个队列内容属于某个活着的 ID，更新本地结构体以供落盘
                if conv_id in conversations:
                    if 'messages' not in conversations[conv_id]:
                        conversations[conv_id]['messages'] = []
                    
                    msgs = conversations[conv_id]['messages']
                    # 尽可能合并最后一条 AI 消息避免结构过于碎片化
                    if msgs and msgs[-1]['type'] == 'ai':
                        msgs[-1]['content'] += content
                    else:
                        msgs.append({'type': 'ai', 'content': content, 'timestamp': datetime.now().isoformat()})
                    needs_save = True

                # 立刻 Socket 推送到网页
                socketio.emit('orchestrator_output', {'content': content, 'conv_id': conv_id})
            
            # 限制落盘频率，最多两秒刷写一次硬盘，保护硬盘且防卡顿
            if needs_save and (time.time() - last_save_time > 2):
                save_conversations()
                last_save_time = time.time()
        except Exception:
            pass
        time.sleep(0.05) # 短暂休眠，别把 CPU 跑崩了

# ==========================================
# Flask 路由与 HTTP API 定义
# ==========================================

# 根路由：返回包含前台业务原型的 HTML 长文本
@app.route('/')
def index():
    # 【修改处 2】：使用 make_response 包装模板，以便我们能够修改 HTTP 响应头
    response = make_response(HTML_TEMPLATE)
    
    # 🌟 终极反缓存策略：强制告诉所有普通浏览器“不要缓存这个页面！”
    # Cache-Control: no-store 禁止任何形式的本地落盘缓存
    # must-revalidate 强制每次都向服务器验证版本
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    # 兼容老式 HTTP/1.0 浏览器的防缓存头
    response.headers["Pragma"] = "no-cache"
    # 设置过期时间为 0，代表立刻过期
    response.headers["Expires"] = "0"
    
    return response

# 查询历史所有对话列表元信息（供左侧边栏使用）
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    conv_list = []
    for conv_id, conv in conversations.items():
        if not isinstance(conv, dict): continue
        conv_list.append({
            'id': conv_id, 
            'title': conv.get('title', "未命名"), 
            'updated_at': str(conv.get('updated_at', '1970-01-01T00:00:00'))
        })
    conv_list.sort(key=lambda x: x['updated_at'], reverse=True) 
    return jsonify(conv_list)

# 单独获取某一次对话内部全部 message 用以重新渲染前端面板
@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    conv = conversations.get(conversation_id, {})
    if 'messages' not in conv:
        conv['messages'] = []
    return jsonify(conv)

# 删除动作对应的 HTTP 接口
@app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    if conversation_id in conversations:
        del conversations[conversation_id]
        save_conversations()
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Not found'}), 404

# 建构一个全新空白对话的占位符写入 json 中
@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    conversation_id = str(uuid.uuid4())
    conversations[conversation_id] = {
        'id': conversation_id, 'title': "待初始化", 'updated_at': datetime.now().isoformat(), 'messages': []
    }
    save_conversations()
    return jsonify({'conversation_id': conversation_id})

# 用户点击页面下方的【执行】后调用的 POST 处理主干
@app.route('/api/conversations/<conversation_id>/execute', methods=['POST'])
def execute_task(conversation_id):
    data = request.get_json()
    lab_name = data.get('lab_name')
    fault_name = data.get('fault_name')
    max_steps = data.get('max_steps', 50)
    frozen_title = data.get('title')
    
    if conversation_id not in conversations:
        return jsonify({'error': 'Not found'}), 404
        
    # 同步状态入内存
    conversations[conversation_id]['title'] = frozen_title
    if 'messages' not in conversations[conversation_id]:
        conversations[conversation_id]['messages'] = []
        
    # 添加用户的模拟发送记录
    conversations[conversation_id]['messages'].append({
        'type': 'user', 'content': f"【执行排障任务】 场景: {lab_name} | 故障: {fault_name} | 最大步数: {max_steps}", 'timestamp': datetime.now().isoformat()
    })
    
    # 填装用于开启打字机宿主的首句系统消息
    conversations[conversation_id]['messages'].append({
        'type': 'ai', 'content': "> [System] Orchestrator Agent 引擎启动...\n", 'timestamp': datetime.now().isoformat()
    })
    
    conversations[conversation_id]['updated_at'] = datetime.now().isoformat()
    save_conversations()
    
    # 将实际需要耗时运行的任务分离出一个全新线程，以免阻塞 Flask 的 Web 响应
    thread = threading.Thread(target=run_orchestrator_task, args=(conversation_id, lab_name, fault_name, max_steps))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'processing'})

# 项目系统主入口
if __name__ == '__main__':
    conversations = load_conversations()
    
    # 唤起后方的队列输出推流线程
    output_thread = threading.Thread(target=output_monitor)
    output_thread.daemon = True
    output_thread.start()
    
    print("\n" + "="*50)
    print("🚀 Web UI (无频道防断连版) 已启动！")
    print("👉 必须在浏览器无痕模式强制刷新访问: http://127.0.0.1:5055")
    print("="*50 + "\n")
    
    # 基于 SocketIO 服务器启动服务
    socketio.run(app, host='0.0.0.0', port=5055, debug=False)











# ======================= 原始版本 ===================== #
# import os
# os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
# os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

# from flask import Flask, request, jsonify
# from flask_socketio import SocketIO
# import json
# import uuid
# import time
# import threading
# import sys
# import asyncio
# import logging
# import re
# from queue import Queue
# from datetime import datetime
# import traceback

# # ==========================================
# # 解决环境路径与导包报错
# # ==========================================
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.abspath(os.path.join(current_dir, ".."))
# if current_dir not in sys.path:
#     sys.path.insert(0, current_dir)

# try:
#     from orchestrator import Orchestrator
#     global_orchestrator = Orchestrator()
#     print(">>> 成功加载 Orchestrator 核心模块！")
# except ImportError as e:
#     print(f">>> 警告: 无法加载 orchestrator.py，错误信息: {e}")
#     global_orchestrator = None

# app = Flask(__name__)
# app.config['SECRET_KEY'] = 'your-secret-key'
# socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

# conversations = {}          
# output_queue = Queue()      
# active_conv_id = None       
# CONVERSATIONS_FILE = 'conversations.json'

# # ==========================================
# # 🌟 终极解决方案：同时接管 Web 输出、System.log 和 Case.log 的拦截器！
# # ==========================================
# class UnifiedOutputInterceptor:
#     def __init__(self, orig_stream):
#         self.orig = orig_stream
#         self.lock = threading.Lock() 
        
#         # 准备全局 System.log 路径
#         self.sys_log_path = os.path.join(project_root, "runtime", "system.log")
#         os.makedirs(os.path.dirname(self.sys_log_path), exist_ok=True)
        
#         self.case_log_file = None

#     def start_case_log(self, lab_name, fault_name):
#         """前端点击执行时，动态开辟一个当前 case 的独立日志文件"""
#         with self.lock:
#             if self.case_log_file:
#                 try: self.case_log_file.close()
#                 except: pass
#             case_dir = os.path.join(project_root, "runtime", "cases")
#             os.makedirs(case_dir, exist_ok=True)
#             path = os.path.join(case_dir, f"{lab_name}_{fault_name}.log")
#             self.case_log_file = open(path, "a", encoding="utf-8")

#     def stop_case_log(self):
#         """执行结束时关闭独立文件"""
#         with self.lock:
#             if self.case_log_file:
#                 try: self.case_log_file.close()
#                 except: pass
#                 self.case_log_file = None

#     def write(self, text):
#         with self.lock:
#             # 1. 打印到原始终端 (控制台)
#             try:
#                 self.orig.write(text)
#                 self.orig.flush()
#             except: pass
            
#             # 2. 同步写入系统日志文件和 Case 日志文件
#             try:
#                 if isinstance(text, str):
#                     # 追加到 runtime/system.log
#                     with open(self.sys_log_path, "a", encoding="utf-8") as f:
#                         f.write(text)
#                     # 追加到 runtime/cases/xxx.log
#                     if self.case_log_file:
#                         self.case_log_file.write(text)
#                         self.case_log_file.flush()
#             except: pass
            
#             # 3. 推送给前端网页
#             try:
#                 global active_conv_id
#                 if active_conv_id and isinstance(text, str) and text:
#                     clean_text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
#                     if clean_text:
#                         output_queue.put(('output', clean_text, active_conv_id))
#             except: pass

#     def flush(self):
#         try: self.orig.flush()
#         except: pass

# global_stdout = UnifiedOutputInterceptor(sys.stdout)
# sys.stdout = global_stdout


# # ==========================================
# # 前端 HTML/CSS/JS 原生模板
# # ==========================================
# # ==========================================
# # 前端 HTML/CSS/JS 原生模板 (请完全替换这一段)
# # ==========================================
# HTML_TEMPLATE = """
# <!DOCTYPE html>
# <html lang="zh-CN">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>PlayGround Network Diagnosis</title>
#     <script src="https://cdn.bootcdn.net/ajax/libs/socket.io/4.0.1/socket.io.min.js"></script>
#     <style>
#         /* === 根节点颜色变量定义，方便全局统一调整 UI 主题 === */
#         :root {
#             --border-light: #e0e0e0; 
#             --border-medium: #cccccc;
#             --border-dark: #999999;  
#             --bg-color: #ffffff;     
#             --bg-hover: #f5f5f5;     
#             --bg-chat-user: #000000; 
#             --text-user: #ffffff;    
#             --bg-chat-ai: #f9f9f9;   
#             --text-main: #000000;    
#             --text-muted: #666666;   
#         }
        
#         * { box-sizing: border-box; margin: 0; padding: 0; }
        
#         /* body: 整个页面的根容器。采用 Flex 左右布局，禁止浏览器本身的滚动条 (overflow: hidden) */
#         body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: var(--bg-color); color: var(--text-main); height: 100vh; display: flex; overflow: hidden; }
        
#         /* === 左区 (对话历史侧边栏) === */
#         /* width: 240px 固定宽度；flex-shrink: 0 防止被右侧内容挤压变窄 */
#         #left-zone { width: 240px; height: 100%; border-right: 1px solid var(--border-medium); display: flex; flex-direction: column; background: #fff; flex-shrink: 0; }
#         #left-zone h3 { text-align: center; padding: 15px 0; font-size: 16px; border-bottom: 1px solid var(--border-light); font-weight: normal; }
        
#         /* 新建对话按钮 */
#         #new-chat-btn { margin: 10px; padding: 8px; background: #000; color: #fff; text-align: center; cursor: pointer; border: 1px solid #000; font-size: 14px; transition: 0.2s; }
#         #new-chat-btn:hover { background: #333; }
        
#         /* 历史列表：占据左侧剩余的所有高度 (flex: 1)，内容超长时允许内部纵向滚动 (overflow-y: auto) */
#         #history-list { flex: 1; overflow-y: auto; list-style: none; padding: 0; }
#         .history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 15px; border-bottom: 1px solid var(--border-light); cursor: pointer; font-size: 12px; color: var(--text-muted); transition: background 0.2s; }
#         .history-item:hover, .history-item.active { background: var(--bg-hover); color: var(--text-main); }
#         .history-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
#         .delete-btn { font-size: 14px; padding: 2px 6px; border-radius: 4px; cursor: pointer; opacity: 0.5; transition: 0.2s; }
#         .delete-btn:hover { opacity: 1; background: #ffe6e6; color: #d00; }
        
#         /* === 右侧大区 (包含顶部导航、中间聊天、底部操作台) === */
#         /* flex: 1 占据屏幕剩余的所有宽度；内部纵向排布 (flex-direction: column) */
#         #right-container { flex: 1; display: flex; flex-direction: column; height: 100%; min-width: 0; }
        
#         /* 右上区 (Top Bar): 固定高度 60px */
#         #top-right-zone { height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid var(--border-medium); flex-shrink: 0; }
#         .logo { font-size: 28px; font-weight: bold; letter-spacing: -0.5px; }
#         .session-title { font-size: 16px; color: var(--text-muted); text-align: center; flex: 1; font-weight: 600;}
        
#         /* === 中间区 (聊天日志展示面板) === */
#         /* flex: 1 占据页面中部全部高度。当聊天内容变多时，这里会出现滚动条 */
#         #middle-zone { flex: 1; overflow-y: auto; padding: 20px; background: #fafafa; display: flex; flex-direction: column; gap: 15px; border-bottom: 1px solid var(--border-medium); }
        
#         /* 🌟 聊天气泡的横向包裹容器：保证头像和气泡能并排同行显示 */
#         .msg-row { display: flex; width: 100%; align-items: flex-start; gap: 10px; }
#         .row-user { justify-content: flex-end; }  /* 用户的行：内容向右对齐 */
#         .row-ai { justify-content: flex-start; }  /* AI的行：内容向左对齐 */
        
#         /* 角色文字与 Emoji 头像的样式 */
#         .msg-avatar { font-size: 13px; font-weight: bold; color: #555; white-space: nowrap; padding-top: 10px; user-select: none; }
        
#         /* 气泡基础公共样式：限制文字换行规则，定义内边距 */
#         .message { padding: 12px 16px; border-radius: 4px; font-size: 14px; line-height: 1.6; word-wrap: break-word; white-space: pre-wrap;}
        
#         /* 用户气泡：黑底白字，最大宽度 75%，防止文字过少时框显得太大 */
#         .msg-user { background: var(--bg-chat-user); color: var(--text-user); max-width: 75%; }
        
#         /* 🌟 AI 气泡：极客灰白底色，采用代码等宽字体(monospace)。加宽处理：最大允许占据 90% 的页面宽度！ */
#         .msg-ai { background: var(--bg-chat-ai); border: 1px solid var(--border-light); color: var(--text-main); font-family: Consolas, monospace; width: 90%; max-width: 90%; }
        
#         /* 系统消息(如: "系统已就绪")：虚线框，没有头像，但要往右挤 75px，以便和 AI 气泡在视觉上对其 */
#         .msg-sys { align-self: flex-start; background: transparent; color: var(--text-muted); font-size: 12px; border: 1px dashed var(--border-light); margin-left: 75px; }
        
#         /* === 底部大区 (控制台总容器) === */
#         /* height: 320px 固定整个底部控制台的高度，不管你怎么缩放浏览器，底部高度不变 */
#         #bottom-container { height: 320px; display: flex; flex-shrink: 0; background: #fff; }
        
#         /* === 底部左区 (网络场景 6宫格 + 运行输入框) === */
#         /* flex: 5 代表如果把底部切成 11 份，左边占 5 份宽度 */
#         #bottom-zone { flex: 5; display: flex; flex-direction: column; border-right: 1px solid var(--border-medium); padding: 15px; }
        
#         /* 输入操作区包裹框：固定高度 80px */
#         .input-area { display: flex; gap: 10px; margin-bottom: 15px; height: 80px;}
#         /* 用户输入的大文本框 */
#         #user-input { flex: 1; resize: none; padding: 10px; border: 1px solid var(--border-dark); font-family: inherit; font-size: 14px; outline: none; }
#         #user-input:focus { border-color: #000; }
        
#         /* 执行按钮与步数输入的包裹框：宽度定死 140px */
#         .action-area { display: flex; flex-direction: column; width: 140px; gap: 6px; } 
#         .action-area input { flex: 1; text-align: center; border: 1px solid var(--border-dark); font-size: 12px; outline: none; }
#         .action-area input:focus { border-color: #000; }
#         .action-area button { flex: 1; background: #000; color: #fff; border: none; cursor: pointer; font-size: 14px; transition: 0.2s; font-weight: bold;}
#         .action-area button:hover { background: #333; }
        
#         .section-title { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; font-weight: bold;}
        
#         /* 场景按钮：采用网格布局(Grid)，固定 3 列、2 行 */
#         #scenarios-grid { display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(2, 1fr); gap: 8px; flex: 1; }
        
#         /* === 底部右区 (故障注入选区) === */
#         /* flex: 6 代表右边占 6 份宽度 */
#         #bottom-right-zone { flex: 6; padding: 15px; display: flex; flex-direction: column; min-width: 0; }
        
#         /* 🌟 故障按钮网格：横向拖动修改点 */
#         #faults-grid { 
#             display: grid; 
#             grid-template-rows: repeat(4, 1fr); /* 强制固定为 4 行 */
#             grid-auto-columns: 160px;           /* 🌟 每一个按钮的宽度强制加大到 160px，足够容纳超长的英文名 */
#             grid-auto-flow: column;             /* 当按钮超出 4 行时，自动往"右侧(下一列)"增加，而不是往下掉 */
#             gap: 8px; 
#             overflow-x: auto;                   /* 🌟 允许横向拖动出现滚动条 */
#             overflow-y: hidden;                 /* 绝对禁止纵向滚动 */
#             flex: 1; 
#             padding-bottom: 8px;                /* 给底部的滚动条留出一点空间 */
#         }
        
#         /* 自定义底部的横向滚动条样式（让它好看一点） */
#         #faults-grid::-webkit-scrollbar { height: 8px; }
#         #faults-grid::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
#         #faults-grid::-webkit-scrollbar-thumb { background: #bbb; border-radius: 4px; }
#         #faults-grid::-webkit-scrollbar-thumb:hover { background: #888; }
        
#         /* 按钮内部文字布局：上下排列对齐 */
#         .btn { border: 1px solid var(--border-medium); background: #fff; color: #000; cursor: pointer; padding: 4px; text-align: center; display: flex; align-items: center; justify-content: center; flex-direction: column; transition: 0.1s; line-height: 1.2;}
#         .btn span.en { font-weight: bold; margin-bottom: 2px; font-size: 12px;}  /* 英文名 */
#         .btn span.cn { font-size: 11px; color: #555; margin-bottom: 2px;}         /* 中文名 */
#         .btn span.topo { font-size: 10px; color: #1a73e8; font-weight: bold;}     /* 🌟 蓝色的最佳适配拓扑名 */
        
#         .btn:hover { border-color: #000; background: #f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
        
#         /* 运行任务时的页面冻结特效 */
#         .readonly-overlay { pointer-events: none; opacity: 0.5; filter: grayscale(100%); }
#     </style>
# </head>
# <body>
#     <div id="left-zone">
#         <h3>对话历史</h3>
#         <div id="new-chat-btn">+ 新建对话</div>
#         <ul id="history-list"></ul>
#     </div>
#     <div id="right-container">
#         <div id="top-right-zone">
#             <div class="logo">PlayGround</div>
#             <div class="session-title" id="session-title">准备就绪</div>
#             <div style="width: 100px;"></div> </div>
#         <div id="middle-zone">
#             <div class="message msg-sys">系统已就绪。请从下方选择场景与故障以发起测试任务。</div>
#         </div>
#         <div id="bottom-container">
#             <div id="bottom-zone">
#                 <div class="section-title">网络场景 (Scenarios - 6种)</div>
#                 <div id="scenarios-grid"></div>
#                 <div class="input-area" style="margin-top: 15px;">
#                     <textarea id="user-input" placeholder="输入自然语言(暂未接入Agent对话功能)，或点击右侧执行..."></textarea>
#                     <div class="action-area">
#                         <input type="number" id="max-steps-input" placeholder="Agent尝试次数" value="50" title="Agent 最大尝试次数">
#                         <button id="send-btn">执行</button>
#                     </div>
#                 </div>
#             </div>
#             <div id="bottom-right-zone">
#                 <div class="section-title">故障注入选区 (Faults - 28种) <span style="font-weight:normal;color:#1a73e8;">← 鼠标放此横向拖动查看全部 →</span></div>
#                 <div id="faults-grid"></div>
#             </div>
#         </div>
#     </div>

# <script>
#     const socket = io();
#     let currentConvId = null; 
#     let labName = null;       
#     let faultName = null;     
#     let isReadOnly = false;   
#     let frozenTitle = null;   

#     // 数据：6大网络场景
#     const scenarios = [
#         { id: "static_routing", name: "静态路由" }, { id: "simple_bgp", name: "简单 BGP" },
#         { id: "ospf_enterprise", name: "OSPF 企业网" }, { id: "rip_internet", name: "RIP 小型网络" },
#         { id: "sdn_openflow", name: "SDN 网络" }, { id: "p4_star", name: "P4 星型网络" }
#     ];

#     // 🌟 数据修改：为 28 种故障人工增加了 best_topo (最佳适配拓扑) 字段，用于按钮蓝字渲染
#     const faults = [
#         { id: "ip_misconfig", name: "IP配置错误", best_topo: "static_routing" }, 
#         { id: "default_route_missing", name: "缺默认路由", best_topo: "static_routing" },
#         { id: "arp_poisoning", name: "ARP投毒", best_topo: "static_routing" }, 
#         { id: "interface_down", name: "接口DOWN", best_topo: "static_routing" },
#         { id: "dns_error", name: "DNS错误", best_topo: "static_routing" }, 
#         { id: "high_cpu_load", name: "CPU满载", best_topo: "static_routing" },
#         { id: "route_missing", name: "路由丢失", best_topo: "static_routing" }, 
#         { id: "static_route_blackhole", name: "黑洞路由", best_topo: "static_routing" },
#         { id: "router_data_plane_drop", name: "数据面丢弃", best_topo: "static_routing" }, 
#         { id: "bgp_neighbor_shutdown", name: "BGP邻居断", best_topo: "simple_bgp" },
#         { id: "bgp_withdraw_route", name: "BGP路由撤销", best_topo: "simple_bgp" }, 
#         { id: "bgp_wrong_peer_asn", name: "BGP AS错", best_topo: "simple_bgp" },
#         { id: "ospf_passive_interface", name: "OSPF被动接口", best_topo: "ospf_enterprise" }, 
#         { id: "ospf_cost_spike", name: "OSPF开销增", best_topo: "ospf_enterprise" },
#         { id: "ospf_daemon_crash", name: "OSPF进程崩", best_topo: "ospf_enterprise" }, 
#         { id: "rip_passive_interface", name: "RIP被动接口", best_topo: "rip_internet" },
#         { id: "rip_route_filter", name: "RIP路由过滤", best_topo: "rip_internet" }, 
#         { id: "rip_metric_offset", name: "RIP跳数篡改", best_topo: "rip_internet" },
#         { id: "sdn_controller_crash", name: "SDN控制器崩", best_topo: "sdn_openflow" }, 
#         { id: "ovs_disconnect_controller", name: "OVS断连", best_topo: "sdn_openflow" },
#         { id: "ovs_global_drop_flow", name: "OVS全局丢弃", best_topo: "sdn_openflow" }, 
#         { id: "bmv2_process_crash", name: "BMV2崩溃", best_topo: "p4_star" },
#         { id: "p4_table_drop", name: "P4流表丢弃", best_topo: "p4_star" }, 
#         { id: "p4_wrong_forwarding", name: "P4转发错", best_topo: "p4_star" },
#         { id: "link_latency", name: "高延迟", best_topo: "simple_bgp" }, 
#         { id: "link_loss", name: "丢包", best_topo: "simple_bgp" },
#         { id: "link_jitter", name: "抖动", best_topo: "simple_bgp" }, 
#         { id: "link_bandwidth", name: "带宽限制", best_topo: "simple_bgp" }
#     ];

#     // ==========================================
#     // 🌟 打字机引擎 (Typewriter Engine)
#     // ==========================================
#     let currentAiBubble = null; // 当前正在活动的 AI 气泡对象
#     let typeQueue = "";         // 打字机缓冲区：存放还没有打印到屏幕上的字符
#     let isTyping = false;       // 打字机状态标识：是否正在执行打字循环

#     // 核心函数：循环从缓冲区拿字，一个一个贴到屏幕上
#     function processTypeQueue() {
#         // 如果缓冲区有字，并且当前的 AI 气泡没有被切换/打断
#         if (typeQueue.length > 0 && currentAiBubble) {
#             // 取出第一个字符，追加到页面上
#             currentAiBubble.innerText += typeQueue.charAt(0);
#             // 将缓冲区剩下的字符重新赋值（相当于移除了刚刚打印的那个字）
#             typeQueue = typeQueue.substring(1);
            
#             // 确保每次打完一个字，聊天框都能自动滚动到最底下
#             const zone = document.getElementById('middle-zone');
#             zone.scrollTop = zone.scrollHeight;
            
#             // 设定一个定时器：多少毫秒后打印下一个字。这里设置的是 10 毫秒（极快打字机的感觉）
#             setTimeout(processTypeQueue, 10);
#         } else {
#             // 缓冲区空了，打字机进入休眠状态
#             isTyping = false;
#         }
#     }

#     // 将消息追加到 UI 的控制枢纽
#     function appendMessage(sender, content, appendMode = false) {
#         const zone = document.getElementById('middle-zone');
        
#         // 🌟【流式追加分支】：如果是后台连续源源不断送来的字 (appendMode=true)
#         if (appendMode && currentAiBubble && sender === 'ai') {
#             typeQueue += content; // 把后端发来的最新片段，塞进打字机缓冲区的尾巴
#             if (!isTyping) {      // 如果打字机在睡觉，踹醒它开始工作
#                 isTyping = true;
#                 processTypeQueue();
#             }
#             return; // 追加完就直接结束，不往下执行“新建一行”的操作
#         }
        
#         // 🌟【新建行分支】：如果是全新的对话（如用户发言，或后台全新开始）
#         typeQueue = ""; // 强制清空旧的打字机残余，防止串台
#         isTyping = false;
        
#         const rowDiv = document.createElement('div');
#         const bubbleDiv = document.createElement('div');
#         bubbleDiv.innerText = content; // 新气泡的初始内容直接放入
        
#         if (sender === 'user') {
#             // 【用户消息构造】：右对齐，右边带 You 的 Emoji
#             rowDiv.className = 'msg-row row-user';
#             bubbleDiv.className = 'message msg-user';
#             const avatar = document.createElement('div');
#             avatar.className = 'msg-avatar';
#             avatar.innerText = 'You 🧑‍💻'; 
            
#             rowDiv.appendChild(bubbleDiv); // 先放气泡
#             rowDiv.appendChild(avatar);    // 再放头像 (气泡在左，头像在右)
            
#             currentAiBubble = null; // 用户发言会打断 AI 的气泡锚点
#             zone.appendChild(rowDiv);
            
#         } else if (sender === 'ai') {
#             // 【AI 消息构造】：左对齐，左边带 Agent 的 Emoji
#             rowDiv.className = 'msg-row row-ai';
#             bubbleDiv.className = 'message msg-ai';
#             const avatar = document.createElement('div');
#             avatar.className = 'msg-avatar';
#             avatar.innerText = '🤖 Agent'; 
            
#             rowDiv.appendChild(avatar);    // 先放头像
#             rowDiv.appendChild(bubbleDiv); // 再放气泡 (头像在左，气泡在右)
            
#             currentAiBubble = bubbleDiv; // 让这个新诞生的黑框，成为后续打字机的承载体！
#             zone.appendChild(rowDiv);
            
#         } else {
#             // 【系统消息构造】：无头像，靠左虚线框
#             bubbleDiv.className = 'message msg-sys';
#             currentAiBubble = null;
#             zone.appendChild(bubbleDiv);
#         }
        
#         zone.scrollTop = zone.scrollHeight; // 追加完新行，滚动到底部
#     }

#     // ==========================================
#     // 页面交互事件绑定与初始化
#     // ==========================================

#     function updateTitle() {
#         if(frozenTitle) { document.getElementById('session-title').innerText = frozenTitle; return; }
#         if(!currentConvId) return;
#         const now = new Date();
#         const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
#         const lName = labName ? labName : "待选场景";
#         const fName = faultName ? faultName : "待选故障";
#         document.getElementById('session-title').innerText = `${dateStr} ${lName} ${fName}`;
#     }

#     // ==========================================
#     // 🌟 修复 1：页面标题更新逻辑
#     // ==========================================
#     function updateTitle() {
#         // 如果任务已经执行，标题被冻结，则直接显示冻结的标题
#         if(frozenTitle) {
#             document.getElementById('session-title').innerText = frozenTitle;
#             return;
#         }
        
#         // 动态生成当前时间字符串，即使还没有创建会话 ID 也能实时走动
#         const now = new Date();
#         const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
#         const lName = labName ? labName : "待选场景";
#         const fName = faultName ? faultName : "待选故障";
        
#         // 实时渲染顶部栏的时间与状态
#         document.getElementById('session-title').innerText = `${dateStr} | ${lName} | ${fName}`;
#     }

#     // 动态生成底部控制台的按钮
#     function renderButtons() {
#         // 渲染 6 种场景按钮
#         const sGrid = document.getElementById('scenarios-grid');
#         scenarios.forEach(s => {
#             let b = document.createElement('button');
#             b.className = 'btn';
#             b.innerHTML = `<span class="en">${s.id}</span><span class="cn">${s.name}</span>`;
#             b.onclick = () => { 
#                 labName = s.id; 
#                 appendMessage('sys', `>> 已选择网络场景: ${s.name} (${s.id})`);
#                 updateTitle(); updateInputBox(); 
#             };
#             sGrid.appendChild(b);
#         });

#         // 渲染 28 种故障按钮
#         const fGrid = document.getElementById('faults-grid');
#         faults.forEach(f => {
#             let b = document.createElement('button');
#             b.className = 'btn';
#             // 🌟 核心：在按钮最底部，利用 span.topo 强行塞入蓝色最佳适配拓扑字样
#             b.innerHTML = `<span class="en">${f.id}</span><span class="cn">${f.name}</span><span class="topo">${f.best_topo}</span>`;
#             b.onclick = () => { 
#                 faultName = f.id; 
#                 appendMessage('sys', `>> 已选择注入故障: ${f.name} (${f.id})`);
#                 updateTitle(); updateInputBox(); 
#             };
#             fGrid.appendChild(b);
#         });
#     }

#     try { renderButtons(); } catch(e) {}

#     // 执行任务期间，锁定界面的 CSS 样式
#     function setMode(readonly) {
#         isReadOnly = readonly;
#         document.getElementById('bottom-container').classList.toggle('readonly-overlay', readonly);
#     }

#     // 后端 API 调用系列函数
#     async function deleteConversation(id, event) {
#         event.stopPropagation(); 
#         if(!confirm("确定要删除这条诊断记录吗？")) return;
#         try {
#             await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
#             if (currentConvId === id) newConversation();
#             else loadHistoryList();
#         } catch(e) { console.error(e); }
#     }

#     async function loadHistoryList() {
#         try {
#             const res = await fetch('/api/conversations');
#             const data = await res.json();
#             const list = document.getElementById('history-list');
#             list.innerHTML = '';
#             data.forEach(c => {
#                 let li = document.createElement('li');
#                 li.className = 'history-item';
#                 li.innerHTML = `<span class="history-title">${c.title || c.id}</span><span class="delete-btn" onclick="deleteConversation('${c.id}', event)">✖</span>`;
#                 li.onclick = (e) => {
#                     if(e.target.classList.contains('delete-btn')) return;
#                     loadConversation(c.id);
#                 };
#                 list.appendChild(li);
#             });
#         } catch(e) {}
#     }

#     async function loadConversation(id) {
#         currentConvId = id;
#         try {
#             const res = await fetch(`/api/conversations/${id}`);
#             const data = await res.json();
#             document.getElementById('middle-zone').innerHTML = ''; 
#             currentAiBubble = null;
#             // 回显历史记录时，关闭追加模式，让消息一条条直接展示即可
#             if(data.messages) {
#                 data.messages.forEach(m => { appendMessage(m.type, m.content, false); });
#             }
#             frozenTitle = data.title; 
#             updateTitle();
#             setMode(true); 
#         } catch(e) {}
#     }

#     // ==========================================
#     // 🌟 修复 2：完全纯前端初始化的新建对话
#     // ==========================================
#     async function newConversation() {
#         try {
#             // 【核心修改】：不再向后端发送 /api/conversations 请求！
#             // 仅仅将前端会话 ID 置空，变成一个不落盘的“幽灵状态”
#             currentConvId = null;
            
#             // 清空聊天面板，放入友好的提示信息
#             document.getElementById('middle-zone').innerHTML = '<div class="message msg-sys">新测试已就绪。请先选择场景和故障，系统将在点击[执行]后自动生成历史记录。</div>';
#             currentAiBubble = null;
            
#             // 重置全部状态变量
#             labName = null; 
#             faultName = null; 
#             frozenTitle = null;
            
#             // 解锁控制台并清空输入框
#             updateInputBox(); 
#             setMode(false); 
#         } catch(e) { 
#             console.error(e); 
#         }
#     }

#     // ==========================================
#     // 🌟 修复 3：带 1 秒延迟与动态创建机制的执行函数
#     // ==========================================
#     async function triggerTask() {
#         if (isReadOnly) return; // 如果正在运行，屏蔽点击
        
#         // 1. 校验用户是否选完了场景和故障
#         if (!labName || !faultName) {
#             alert("请先点击按钮选择【网络场景】和【注入故障】！");
#             return;
#         }
        
#         // 2. 锁定前端界面，获取步数
#         const maxSteps = parseInt(document.getElementById('max-steps-input').value) || 50;
#         setMode(true); 
        
#         // 3. 冻结顶部标题时间
#         frozenTitle = document.getElementById('session-title').innerText;
        
#         // 4. 渲染用户的执行气泡（马上显示，不等那1秒）
#         const taskStr = `【执行排障任务】 场景: ${labName} | 故障: ${faultName} | 最大步数: ${maxSteps}`;
#         appendMessage('user', taskStr);
        
#         // 5. 渲染 AI 的打字机终端接管提示
#         appendMessage('ai', `> [System] Orchestrator Agent 引擎启动...\n> [System] 正在记录同步输出流，请稍候...\n\n`, false);

#         // 🌟【核心修改】：设定 1 秒延迟定时器，1 秒后才会真正发给后端并落盘
#         setTimeout(async () => {
#             try {
#                 // 如果当前是一个全新的幽灵会话，就在这 1 秒后临时向后端请求生成真正的会话 ID
#                 if (!currentConvId) {
#                     const res = await fetch('/api/conversations', { method: 'POST' });
#                     const data = await res.json();
#                     currentConvId = data.conversation_id; // 拿到后端分配的真实 UUID
                    
#                     // 让 WebSocket 加入当前专属频段，准备接收 Agent 日志
#                     if(socket) socket.emit('join_conversation', { conversation_id: currentConvId });
#                 }

#                 // 正式向后端派发执行排障 Agent 的命令
#                 await fetch(`/api/conversations/${currentConvId}/execute`, {
#                     method: 'POST',
#                     headers: { 'Content-Type': 'application/json' },
#                     body: JSON.stringify({ 
#                         lab_name: labName, 
#                         fault_name: faultName, 
#                         max_steps: maxSteps, 
#                         title: frozenTitle 
#                     })
#                 });
                
#                 // 执行成功后，刷新左侧的历史记录列表（此时用户就能看到刚创建的那条记录了）
#                 loadHistoryList(); 
                
#             } catch (e) {
#                 console.error("执行任务失败:", e);
#                 appendMessage('sys', "【系统警告】后端请求失败，请检查控制台。");
#                 setMode(false); // 失败则解锁面板
#             }
#         }, 500); // 500 毫秒 = 0.5 秒
#     }

#     // 绑定按钮点击事件
#     document.getElementById('send-btn').onclick = triggerTask;
#     document.getElementById('new-chat-btn').onclick = newConversation;

#     // 🌟 后端 WebSocket 接收枢纽
#     socket.on('orchestrator_output', data => {
#         if (data.conv_id === currentConvId) {
#             // 当接收到后台碎片的日志时，开启 appendMode=true 给打字机模块进行处理
#             appendMessage('ai', data.content, true); 
#         }
#     });

#     socket.on('orchestrator_done', data => {
#         if (data.conv_id === currentConvId) {
#             // 任务结束补充总结语
#             appendMessage('ai', `\n> [任务执行结束] `, true);
#             setMode(false);    // 界面解锁
#             loadHistoryList(); // 刷新左侧时间
#         }
#     });

#     try {
#         loadHistoryList();
#         newConversation(); 
#         setInterval(updateTitle, 1000); 
#     } catch(e) {}
# </script>
# </body>
# </html>
# """

# # ==========================================
# # 后端业务逻辑与全局输出队列
# # ==========================================
# def load_conversations():
#     if os.path.exists(CONVERSATIONS_FILE):
#         try:
#             with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         except: pass
#     return {}

# def save_conversations():
#     try:
#         with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
#             json.dump(conversations, f, ensure_ascii=False, indent=2)
#     except Exception:
#         pass

# def run_orchestrator_task(conversation_id, lab_name, fault_name, max_steps):
#     global active_conv_id
#     active_conv_id = conversation_id
    
#     # 🌟 启动记录该对话特定的 Case log 文件！
#     global_stdout.start_case_log(lab_name, fault_name)
    
#     try:
#         if global_orchestrator:
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             loop.run_until_complete(global_orchestrator.run_test(lab_name, fault_name, max_steps=max_steps))
#             result = "排障工作流执行完毕。"
#         else:
#             result = "未检测到 Orchestrator 模块，直接结束。"
#             time.sleep(2)
#     except Exception as e:
#         error_msg = f"Orchestrator 致命错误: {str(e)}\n{traceback.format_exc()}"
#         print(error_msg)
#         result = f"异常中断: {str(e)}"
#     finally:
#         active_conv_id = None
#         # 🌟 关闭当前特定的 Case log 文件
#         global_stdout.stop_case_log()
#         socketio.emit('orchestrator_done', {'result': result, 'conv_id': conversation_id})

# def output_monitor():
#     last_save_time = time.time()
#     while True:
#         try:
#             needs_save = False
#             while not output_queue.empty():
#                 msg_type, content, conv_id = output_queue.get()
                
#                 if conv_id in conversations:
#                     if 'messages' not in conversations[conv_id]:
#                         conversations[conv_id]['messages'] = []
                    
#                     msgs = conversations[conv_id]['messages']
#                     if msgs and msgs[-1]['type'] == 'ai':
#                         msgs[-1]['content'] += content
#                     else:
#                         msgs.append({'type': 'ai', 'content': content, 'timestamp': datetime.now().isoformat()})
#                     needs_save = True

#                 socketio.emit('orchestrator_output', {'content': content, 'conv_id': conv_id})
            
#             if needs_save and (time.time() - last_save_time > 2):
#                 save_conversations()
#                 last_save_time = time.time()
#         except Exception:
#             pass
#         time.sleep(0.05)

# # ==========================================
# # Flask 路由与 API 定义
# # ==========================================

# @app.route('/')
# def index():
#     return HTML_TEMPLATE 

# @app.route('/api/conversations', methods=['GET'])
# def get_conversations():
#     conv_list = []
#     for conv_id, conv in conversations.items():
#         if not isinstance(conv, dict): continue
#         conv_list.append({
#             'id': conv_id, 
#             'title': conv.get('title', "未命名"), 
#             'updated_at': str(conv.get('updated_at', '1970-01-01T00:00:00'))
#         })
#     conv_list.sort(key=lambda x: x['updated_at'], reverse=True) 
#     return jsonify(conv_list)

# @app.route('/api/conversations/<conversation_id>', methods=['GET'])
# def get_conversation(conversation_id):
#     conv = conversations.get(conversation_id, {})
#     if 'messages' not in conv:
#         conv['messages'] = []
#     return jsonify(conv)

# @app.route('/api/conversations/<conversation_id>', methods=['DELETE'])
# def delete_conversation(conversation_id):
#     if conversation_id in conversations:
#         del conversations[conversation_id]
#         save_conversations()
#         return jsonify({'status': 'success'})
#     return jsonify({'error': 'Not found'}), 404

# @app.route('/api/conversations', methods=['POST'])
# def create_conversation():
#     conversation_id = str(uuid.uuid4())
#     conversations[conversation_id] = {
#         'id': conversation_id, 'title': "待初始化", 'updated_at': datetime.now().isoformat(), 'messages': []
#     }
#     save_conversations()
#     return jsonify({'conversation_id': conversation_id})

# @app.route('/api/conversations/<conversation_id>/execute', methods=['POST'])
# def execute_task(conversation_id):
#     data = request.get_json()
#     lab_name = data.get('lab_name')
#     fault_name = data.get('fault_name')
#     max_steps = data.get('max_steps', 50)
#     frozen_title = data.get('title')
    
#     if conversation_id not in conversations:
#         return jsonify({'error': 'Not found'}), 404
        
#     conversations[conversation_id]['title'] = frozen_title
#     if 'messages' not in conversations[conversation_id]:
#         conversations[conversation_id]['messages'] = []
        
#     conversations[conversation_id]['messages'].append({
#         'type': 'user', 'content': f"【执行排障任务】 场景: {lab_name} | 故障: {fault_name} | 最大步数: {max_steps}", 'timestamp': datetime.now().isoformat()
#     })
    
#     conversations[conversation_id]['messages'].append({
#         'type': 'ai', 'content': "> [System] Orchestrator Agent 引擎启动...\n> [System] 正在记录同步输出流，请稍候...\n\n", 'timestamp': datetime.now().isoformat()
#     })
    
#     conversations[conversation_id]['updated_at'] = datetime.now().isoformat()
#     save_conversations()
    
#     thread = threading.Thread(target=run_orchestrator_task, args=(conversation_id, lab_name, fault_name, max_steps))
#     thread.daemon = True
#     thread.start()
    
#     return jsonify({'status': 'processing'})

# if __name__ == '__main__':
#     conversations = load_conversations()
#     output_thread = threading.Thread(target=output_monitor)
#     output_thread.daemon = True
#     output_thread.start()
    
#     print("\n" + "="*50)
#     print("🚀 Web UI (无频道防断连版) 已启动！")
#     print("👉 必须在浏览器无痕模式强制刷新访问: http://127.0.0.1:5055")
#     print("="*50 + "\n")
#     socketio.run(app, host='0.0.0.0', port=5055, debug=False)