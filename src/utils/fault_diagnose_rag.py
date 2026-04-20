import os       
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1" # No Proxy 提到前面

import warnings 
import logging
import subprocess # 用于执行 docker 命令
import time       # 用于等待容器启动
import socket     # 用于检测 Milvus 端口是否就绪
import re         # 【新增】用于正则解析标题元数据
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 载入全局 .env

# ==========================================
# 第二部分：代理屏蔽与离线模式
# ==========================================
os.environ["HF_HUB_OFFLINE"] = "1"       # 告诉 huggingface_hub 库：别联网
os.environ["TRANSFORMERS_OFFLINE"] = "1"  # 告诉 transformers 库：别联网

# 通过环境变量彻底关掉 HuggingFace Hub 底层可能的下载进度条
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_VERBOSITY"] = "error"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 【新增核心】配置虚拟 Token，欺骗鉴权机制，消除未授权警告
os.environ["HF_TOKEN"] = "hf_dummy_token_to_suppress_warning"

# 【新增核心】强制屏蔽 huggingface_hub 的底层 Python logging 警告
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
warnings.filterwarnings("ignore") # 屏蔽所有 Python 的 Warning 输出

# 【模型存放目录】
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "rag_models"))
DOC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "docs"))
os.makedirs(MODEL_DIR, exist_ok=True) # 如果 rag_models 文件夹不存在，就自动创建
os.environ["HF_HOME"] = MODEL_DIR # 告诉 HuggingFace：你的"家"在 MODEL_DIR
os.environ["HF_HUB_CACHE"] = MODEL_DIR # 告诉 HuggingFace Hub：缓存目录也在 MODEL_DIR
warnings.filterwarnings("ignore") # 屏蔽所有 Python 的 Warning 输出

# ==========================================
# 第三部分：导入第三方库
# ==========================================
# 强行通过 transformers 内部日志 API 禁用加载进度条
import transformers
transformers.utils.logging.set_verbosity_error()
transformers.utils.logging.disable_progress_bar()

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.documents import Document # 文档对象, 包括 page_content(正文) 和 metadata(元数据)
from sentence_transformers import CrossEncoder
from pymilvus import MilvusClient, DataType # Milvus 的字段类型枚举, 用来定义 Schema (表结构)
import jieba
from rank_bm25 import BM25Plus
jieba.setLogLevel(logging.WARNING) # 强制屏蔽 jieba 内部的构建字典提示

from .network_domain_words import DOMAIN_WORDS


# ==========================================
# 故障层级优先级配置（先验知识）
# ==========================================
FAULT_LEVEL_PRIORITY = {
    # 链路层故障影响范围最大，优先级最高
    "Link Level": 1.4,
    
    # 路由协议故障影响域间通信，优先级次高
    "BGP Level": 1.2,
    "OSPF Level": 1.2,
    "RIP Level": 1.2,
    "FRR Level": 1.2,

    # 数据平面故障影响转发，优先级中等偏高
    "P4 Level": 1.15,
    "SDN Level": 1.15,
    
    # 主机层故障影响单点，优先级中等
    "Host Level": 1.0,
    
    # AI 推理故障影响应用层，优先级基准
    "AI Inference Level": 1.0,
}

def get_fault_level_from_metadata(metadata: dict) -> str:
    """
    从文档元数据中推断故障层级
    
    推断规则：
    1. 从 fault_name 推断（如 link_loss -> Link Level）
    2. 从 node_type 推断（如 "frr 路由器" -> FRR Level）
    3. 默认返回 "Host Level"
    """
    fault_name = metadata.get("fault_name", "").lower()
    node_type = metadata.get("node_type", "").lower()
    
    # 规则 1: 根据故障名称判断
    if "link" in fault_name:
        return "Link Level"
    elif "bgp" in fault_name:
        return "BGP Level"
    elif "ospf" in fault_name:
        return "OSPF Level"
    elif "rip" in fault_name:
        return "RIP Level"
    elif "p4" in fault_name:
        return "P4 Level"
    elif "ovs" in fault_name or "sdn" in fault_name or "flow" in fault_name or "southbound" in fault_name:
        return "SDN Level"
    elif "ai" in fault_name or "compute" in fault_name or "inference" in fault_name or "rst" in fault_name or "layer" in fault_name:
        return "AI Inference Level"
    elif fault_name in ["route_missing", "static_route_blackhole", "data_plane_drop", 
                        "frr_service_down", "ip_forward_disabled", "router_interface_ip_wrong"]:
        return "FRR Level"
    
    # 规则 2: 根据节点类型判断
    if "frr" in node_type or "路由器" in node_type:
        return "FRR Level"
    elif "bmv2" in node_type or "p4" in node_type:
        return "P4 Level"
    elif "ovs" in node_type or "ryu" in node_type or "控制器" in node_type:
        return "SDN Level"
    
    # 默认: 主机层故障
    return "Host Level"

# ==========================================
# 第四部分：核心类 FaultDiagnosisKnowledgeBase
# ==========================================
class FaultDiagnosisKnowledgeBase:
    """
    故障诊断知识库：一个完整的 RAG 系统
    
    建库流程 (首次或 force_rebuild=True)：
    1. 读取 Markdown 故障诊断手册 (fault_diagnose.md)
    2. 按一级标题切分成小块 (每块代表一种故障类型的诊断方法)
    3. 从标题中提取元数据：故障名称、节点类型、适用场景
    4. 每块用 BGE-M3 生成向量，用 Jieba 切分成 token 列表
    5. 把 向量 + 原文 + 元数据(故障名称、节点类型、适用场景) + 切分结果(tokenized_text) 存进 Milvus 数据库
    
    日常加载流程 (数据库已存在)：
    1. 瞬间从 Milvus 拉取所有 text、元数据与 tokenized_text
    2. 在内存中还原 docs 列表与 BM25Plus 模型，跳过重构开销

    查询流程：
    1. 用户提问 + 当前网络场景
    2. 根据适用场景元数据过滤候选文档（"全场景"的文档始终保留）
    3. BM25Plus 关键词检索（路1）+ Milvus 向量检索（路2）
    4. 合并去重 
    5. CrossEncoder 重排精选 
    6. 返回最相关的诊断文档给诊断智能体
    """
    
    def __init__(self, 
                 md_path: str = DOC_DIR,            
                 db_uri: str = os.getenv("MILVUS_URI", "http://127.0.0.1:19530"),  
                 collection_name: str = "fault_diagnose",  
                 force_rebuild: bool = False):      # 是否强制重建数据库
        
        # ----- 1. 确定文件路径 -----
        self.md_path = os.path.join(md_path, "fault_diagnose.md")  # 改为读取故障诊断手册
        self.db_uri = db_uri                    # 保存数据库连接地址
        self.collection_name = collection_name  # 保存集合名
        self._ensure_milvus_running() # 在加载模型和连接数据库之前，先唤醒沉睡的容器

        # ----- 2. 加载 Embedding 模型（向量化模型）-----
        print("[RAG] 正在加载 BGE-M3 向量化模型...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",            # 模型名称：北京智源的 BGE-M3，支持中英文，1024维输出
            model_kwargs={'device': 'cpu'},      # 用 CPU 推理
            encode_kwargs={'normalize_embeddings': True}  # 输出向量做 L2 归一化
        )
        self.embedding_dim = 1024  # BGE-M3 模型输出的向量维度是 1024

        # ----- 3. 加载 Reranker 模型（重排模型）-----
        print("[RAG] 正在加载 BGE-Reranker-v2-M3 重排模型...")
        self.cross_encoder = CrossEncoder(
            model_name_or_path="BAAI/bge-reranker-v2-m3",  # 北京智源的重排模型
            device="cpu",       # 用 CPU 推理
            max_length=1024     # 输入文本最大长度
        )
        
        # ----- 4. 热加载预热 NLP 分词引擎 -----
        self._init_nlp()
        
        # ----- 5. 连接 Milvus 数据库并初始化 -----
        self.docs = []  # 初始化空列表，存储所有文档块
        self.doc_priorities = []  # 【新增】缓存每个文档的层级优先级权重

        print(f"[RAG] 正在连接企业级 Milvus 数据库 ({self.db_uri})...")
        self.client = MilvusClient(uri=self.db_uri)
        
        # 调用智能初始化方法：判断是建新表还是读取旧表恢复数据
        self._smart_init_milvus(force_rebuild) 

    def _init_nlp(self):
        """
        一次性将网络领域专有词典加载进内存，避免运行时冷启动开销
        """
        print("[RAG] 正在预热 jieba NLP 模型与专有名词库...")
        for word in DOMAIN_WORDS:
            jieba.add_word(word)
        # 强行切分一个词，触发 jieba 内部大字典的懒加载机制
        _ = jieba.lcut("故障诊断引擎热加载完成")
        print("[RAG] NLP 模型预热完成！")

    def _ensure_milvus_running(self):
        """
        Docker 状态检查与自启守护
        确保 Milvus 容器组正常运行，若未运行则自动唤醒
        """
        print("[RAG] 正在检查 Milvus 底层容器状态...")
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", "milvus-standalone"],
                capture_output=True, text=True
            )
            if "true" not in result.stdout.lower():
                print("[RAG] 发现 Milvus 容器组未运行，正在自动唤醒...")
                subprocess.run(
                    ["docker", "start", "milvus-etcd", "milvus-minio", "milvus-standalone"], 
                    check=True
                )
                print("[RAG] 容器组已拉起，正在等待 19530 端口服务就绪...")
                port_ready = False

                # 轮询探测端口 (polling)
                for i in range(20):
                    try:
                        with socket.create_connection(("127.0.0.1", 19530), timeout=1):
                            port_ready = True
                            print("[RAG] 端口 19530 通信握手成功，Milvus 服务已完全就绪！")
                            break
                    except OSError:
                        time.sleep(1)
                        print(f"  ... 内部服务初始化中 ({i+1}/20)")
                if not port_ready:
                    print("[RAG] ⚠️ 警告：等待 Milvus 端口就绪超时，接下来的连接可能会失败。")
            else:
                print("[RAG] Milvus 容器组运行正常，无需唤醒。")
        except FileNotFoundError:
            print("[RAG] ❌ 错误：未找到 docker 命令，请确认宿主机环境。")
        except subprocess.CalledProcessError as e:
            print(f"[RAG] ❌ 启动 Docker 容器失败，错误码 {e.returncode}。")

    def _parse_fault_metadata(self, title: str) -> dict:
        """
        从 Markdown 一级标题中提取元数据
        
        注意：传入的 title 已经由 MarkdownHeaderTextSplitter 处理过，不包含 # 符号
        
        标题格式示例: 
        - link_loss (ubuntu 主机) | 全场景
        - interface_down (ubuntu 主机) | 全部场景
        - bgp_neighbor_shutdown (frr 路由器) | simple_bgp
        - ospf_passive_interface (frr 路由器) | ospf_enterprise
        - link_latency (ubuntu 主机) | static_routing, simple_bgp, ospf_enterprise
        
        返回字典包含:
        - fault_name: 故障名称 (如 "link_loss")
        - node_type: 节点类型 (如 "ubuntu 主机")
        - applicable_scenarios: 适用场景列表 (如 ["全场景"] 或 ["static_routing", "simple_bgp"])
        """
        # 使用正则表达式解析标题
        # 匹配模式: 故障名 (节点类型) | 场景1, 场景2, ...
        # 注意：标题已经不包含 # 号
        
        pattern = r'^(\S+)\s+\(([^)]+)\)\s+\|\s+(.+)$'
        match = re.match(pattern, title.strip())
        
        if match:
            fault_name = match.group(1).strip()
            node_type = match.group(2).strip()
            scenarios_str = match.group(3).strip()
            
            # 解析适用场景
            # 统一处理各种"全场景"的变体
            if any(keyword in scenarios_str for keyword in ["全场景", "全部场景", "任意场景", "所有场景"]):
                applicable_scenarios = ["全场景"]
            else:
                # 按逗号分割多个场景，并去除空格
                applicable_scenarios = [s.strip() for s in scenarios_str.split(",") if s.strip()]
                
                # 如果没有解析到任何场景，默认为全场景
                if not applicable_scenarios:
                    applicable_scenarios = ["全场景"]
            
            return {
                "fault_name": fault_name,
                "node_type": node_type,
                "applicable_scenarios": applicable_scenarios
            }
        else:
            # 如果解析失败，尝试更宽松的匹配
            # 可能的格式变体：故障名（节点类型）| 场景（中文括号）
            
            pattern_cn = r'^(\S+)\s+（([^）]+)）\s+\|\s+(.+)$'
            match_cn = re.match(pattern_cn, title.strip())
            
            if match_cn:
                fault_name = match_cn.group(1).strip()
                node_type = match_cn.group(2).strip()
                scenarios_str = match_cn.group(3).strip()
                
                if any(keyword in scenarios_str for keyword in ["全场景", "全部场景", "任意场景", "所有场景"]):
                    applicable_scenarios = ["全场景"]
                else:
                    applicable_scenarios = [s.strip() for s in scenarios_str.split(",") if s.strip()]
                    if not applicable_scenarios:
                        applicable_scenarios = ["全场景"]
                
                return {
                    "fault_name": fault_name,
                    "node_type": node_type,
                    "applicable_scenarios": applicable_scenarios
                }
            
            # 如果两种格式都匹配失败，打印详细的调试信息并返回默认值
            print(f"[RAG] 警告：无法解析标题格式: '{title}'")
            print(f"[RAG] 调试信息：标题 repr={repr(title)}")
            
            # 尝试从标题中至少提取故障名（第一个单词）
            words = title.strip().split()
            fault_name = words[0] if words else "未知故障"
            
            return {
                "fault_name": fault_name,
                "node_type": "未知节点",
                "applicable_scenarios": ["全场景"]  # 默认全场景可用
            }

    def _load_and_split_docs(self):
        """
        【文档切分 + 元数据提取】
        此处仅在 force_rebuild=True 或首次建库时被调用
        
        功能：
        1. 读取 Markdown 故障诊断手册
        2. 按一级标题切分成知识块
        3. 从标题中提取故障名称、节点类型、适用场景等元数据
        4. 将标题信息注入正文（上下文增强）
        """
        print("[RAG] 正在读取本地 Markdown 文档并进行语义切块...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # 按一级标题切分
        headers_to_split_on = [("#", "title")]  # 提取一级标题到 metadata["title"]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        raw_docs = markdown_splitter.split_text(md_content)

        # 【上下文增强 + 元数据提取】
        for doc in raw_docs:
            title = doc.metadata.get("title", "")
            
            # 从标题中提取结构化元数据
            metadata = self._parse_fault_metadata(title)
            
            # 将解析出的元数据合并到文档的 metadata 中
            doc.metadata.update(metadata)
            
            # 把标题信息注入正文，增强上下文
            fault_name = metadata["fault_name"]
            node_type = metadata["node_type"]
            if fault_name and fault_name not in doc.page_content:
                doc.page_content = f"【故障类型：{fault_name}】【节点类型：{node_type}】\n{doc.page_content}"
            
            self.docs.append(doc)
            
            # 【新增】计算并缓存该文档的层级优先级权重
            fault_level = get_fault_level_from_metadata(doc.metadata)
            priority_weight = FAULT_LEVEL_PRIORITY.get(fault_level, 1.0)
            self.doc_priorities.append(priority_weight)
        
        print(f"[RAG] 成功切分并解析了 {len(self.docs)} 个故障诊断知识块。")

    def _smart_init_milvus(self, force_rebuild: bool):
        """
        Milvus 数据库智能初始化 (含全新建库逻辑)
        
        - 若集合存在且不要求重建：直接从 Milvus 提取预先处理好的原文、元数据和 tokenized_text 还原内存环境
        - 若集合不存在或要求重建：走重新解析文件 -> 构筑 Schema -> 切词向量化落库的完整流程
        """
        if self.client.has_collection(collection_name=self.collection_name):
            if force_rebuild:
                print(f"[RAG] 收到强制重建指令，正在摧毁旧集合 '{self.collection_name}'...")
                self.client.drop_collection(collection_name=self.collection_name)
                # 摧毁后继续执行后面的建库逻辑
            else:
                # 【架构升级】不重建时，彻底抛弃本地 MD 读取，直接用数据库做全量内存还原
                print(f"[RAG] 检测到集合 '{self.collection_name}' 已存在且未要求重建，准备从数据库热加载！")
                self.client.load_collection(collection_name=self.collection_name)
                
                print("[RAG] 正在从 Milvus 读取并恢复所有历史原文、元数据与 NLP 分词缓存...")
                # 通过 filter id >= 0 拉取全量实体
                results = self.client.query(
                    collection_name=self.collection_name,
                    filter="id >= 0", 
                    output_fields=["text", "fault_name", "node_type", "applicable_scenarios", "tokenized_text"]
                )
                
                # 开始在内存中还原 self.docs 和 self.bm25_model
                tokenized_corpus = []
                for row in results:
                    # 还原适用场景列表（从逗号分隔的字符串转回列表）
                    scenarios_str = row["applicable_scenarios"]
                    applicable_scenarios = [s.strip() for s in scenarios_str.split(",")]
                    
                    doc = Document(
                        page_content=row["text"], 
                        metadata={
                            "fault_name": row["fault_name"],
                            "node_type": row["node_type"],
                            "applicable_scenarios": applicable_scenarios
                        }
                    )
                    self.docs.append(doc)
                    
                    # 【新增】恢复层级优先级权重缓存
                    fault_level = get_fault_level_from_metadata(doc.metadata)
                    priority_weight = FAULT_LEVEL_PRIORITY.get(fault_level, 1.0)
                    self.doc_priorities.append(priority_weight)
                    
                    # 从空格隔开的数据库字符串还原成 jieba 的二维数组格式
                    tokenized_corpus.append(row["tokenized_text"].split(" "))
                
                # 瞬间构建 BM25 模型，完美绕过重构开销
                self.bm25_model = BM25Plus(tokenized_corpus)
                print(f"[RAG] 成功从数据库缓存还原了 {len(self.docs)} 个知识块，检索系统已就绪！")
                return  # 直接返回，跳过后面的建表和插数据逻辑

        # ==============================================
        # 执行到此处，说明是【首次建库】或【被 Drop 后重建】
        # ==============================================
        print(f"[RAG] 正在创建全新 Schema 并准备从零写入数据...")
        
        # 1. 因为是新建，必须先把本地的 Markdown 读取到 self.docs 中
        self._load_and_split_docs()
        
        # 2. 构建 Schema（表结构），新增元数据字段
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False) 
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        # 【新增元数据字段】
        schema.add_field(field_name="fault_name", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="node_type", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="applicable_scenarios", datatype=DataType.VARCHAR, max_length=2048)  # 存储逗号分隔的场景列表
        # 【分词缓存字段】：空间换时间的核心
        schema.add_field(field_name="tokenized_text", datatype=DataType.VARCHAR, max_length=65535)
        
        # 3. 创建向量索引
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", metric_type="COSINE", index_type="AUTOINDEX")
        
        # 4. 创建集合
        self.client.create_collection(
            collection_name=self.collection_name, 
            schema=schema, 
            index_params=index_params 
        )
        
        # 5. 调用写入逻辑
        self._insert_docs_to_milvus()

    def _insert_docs_to_milvus(self):
        """
        把文档向量化、词频化并写入 Milvus 数据库
        
        功能：
        1. 批量生成语义向量
        2. 执行中文分词并缓存
        3. 将向量、原文、元数据、分词结果一并写入数据库
        """
        print(f"[RAG] 正在生成语义向量与词元划分，并全量同步到 Milvus...")
        
        texts = [doc.page_content for doc in self.docs]
        
        # 1. 批量生成 1024 维密集语义向量
        vectors = self.embeddings.embed_documents(texts)
        
        # 2. 执行写时分词，一并将二维切分结果保存在类中，顺手构造初始的 BM25Plus 模型
        tokenized_corpus = [jieba.lcut(text.lower()) for text in texts]
        self.bm25_model = BM25Plus(tokenized_corpus)
        
        # 3. 数据打包落库
        data = []
        for doc, vector, tokens in zip(self.docs, vectors, tokenized_corpus):
            # 将适用场景列表转为逗号分隔的字符串存储
            scenarios_str = ", ".join(doc.metadata.get("applicable_scenarios", ["全场景"]))
            
            data.append({
                "vector": vector,                                          # 1024 维浮点数组
                "text": doc.page_content,                                  # 原始文本
                "fault_name": doc.metadata.get("fault_name", "未知故障"),    # 故障名称
                "node_type": doc.metadata.get("node_type", "未知节点"),      # 节点类型
                "applicable_scenarios": scenarios_str,                     # 适用场景（逗号分隔）
                "tokenized_text": " ".join(tokens)                         # 分词结果（空格分隔）
            })
            
        self.client.insert(collection_name=self.collection_name, data=data)
        self.client.load_collection(collection_name=self.collection_name)
        print("[RAG] 数据库首次同步写入彻底完成！")

    def _filter_by_scenario(self, docs: list, current_scenario: str) -> list:
        """
        根据当前网络场景过滤文档
        
        过滤规则：
        - 如果文档的 applicable_scenarios 包含 "全场景"，则保留
        - 如果文档的 applicable_scenarios 包含当前场景，则保留
        - 否则过滤掉
        
        参数：
        - docs: 待过滤的文档列表
        - current_scenario: 当前网络场景 (如 "static_routing", "simple_bgp" 等)
        
        返回：
        - 过滤后的文档列表
        """
        if not current_scenario:
            # 如果未指定场景，返回所有文档
            return docs
        
        filtered_docs = []
        for doc in docs:
            applicable_scenarios = doc.metadata.get("applicable_scenarios", ["全场景"])
            
            # 检查是否为全场景或包含当前场景
            if "全场景" in applicable_scenarios or current_scenario in applicable_scenarios:
                filtered_docs.append(doc)
        
        return filtered_docs

    def _fast_prerank(self, query: str, query_vector: list, docs: list, 
                      doc_indices: list, bm25_model, top_k: int = 15) -> list:
        """
        快速预排：使用轻量级特征进行初步排序
        
        策略：
        1. 计算每个文档与 query 的向量余弦相似度（复用已有向量）
        2. 计算 BM25 分数（词频匹配）
        3. 应用故障层级优先级权重（先验知识加成）
        4. 加权融合：0.5 * 向量相似度 + 0.3 * BM25 分数 + 0.2 * 层级权重
        5. 返回 top_k 个文档及其原始索引
        
        参数：
        - query: 用户查询文本
        - query_vector: 查询的向量表示
        - docs: 候选文档列表
        - doc_indices: 文档在 self.docs 中的原始索引（用于获取优先级权重）
        - bm25_model: 基于场景过滤后的 BM25 模型
        - top_k: 返回的文档数量
        
        返回：
        - 排序后的文档列表（不包含索引）
        """
        import numpy as np
        
        if not docs:
            return []
        
        # 1. 计算向量相似度（批量嵌入）
        doc_texts = [doc.page_content for doc in docs]
        doc_vectors = self.embeddings.embed_documents(doc_texts)
        
        query_vec = np.array(query_vector)
        doc_vecs = np.array(doc_vectors)
        
        # 余弦相似度（向量已归一化，直接点积）
        vector_similarities = np.dot(doc_vecs, query_vec)
        
        # 2. 计算 BM25 分数（针对当前候选集重建临时模型）
        tokenized_query = jieba.lcut(query.lower())
        doc_tokenized = [jieba.lcut(text.lower()) for text in doc_texts]
        temp_bm25 = BM25Plus(doc_tokenized)
        bm25_scores = temp_bm25.get_scores(tokenized_query)
        
        # 归一化 BM25 分数到 [0, 1]
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        bm25_normalized = bm25_scores / max_bm25
        
        # 3. 获取每个文档的层级优先级权重
        priority_weights = np.array([self.doc_priorities[idx] for idx in doc_indices])
        
        # 归一化优先级权重到 [0, 1]（相对于最大值）
        max_priority = max(priority_weights) if max(priority_weights) > 0 else 1.0
        priority_normalized = priority_weights / max_priority
        
        # 4. 加权融合（三路特征融合）
        alpha = 0.5  # 向量语义相似度权重（最重要）
        beta = 0.3   # BM25 关键词权重（次要）
        gamma = 0.2  # 层级先验权重（辅助）
        
        combined_scores = (alpha * vector_similarities + 
                          beta * bm25_normalized + 
                          gamma * priority_normalized)
        
        # 5. 排序并返回 top_k
        scored_docs = sorted(zip(docs, combined_scores), key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs[:top_k]]

    def search(self, 
               query: str, 
               current_scenario: str = None, 
               stage1_k: int = 15,      # 第一阶段：粗召回（扩大覆盖面）
               stage2_k: int = 8,      # 第二阶段：快速预排（轻量级过滤）
               final_k: int = 4,        # 第三阶段：精排后返回基准值（自适应调整）
               enable_adaptive: bool = True) -> str:  # 是否启用自适应 final_k
        """
        三阶段渐进式召回 + 自适应重排 + 层级先验知识融合
        
        Stage 0: 场景预过滤（根据网络拓扑场景过滤）
        Stage 1: 双路召回扩大覆盖面（BM25 + Vector，各召回 stage1_k 个）
        Stage 2: 快速预排（向量+BM25+层级权重融合，筛选出 stage2_k 个）
        Stage 3: 交叉编码器精排（只对 stage2_k 个候选重排，自适应返回 final_k 个）
        
        参数调优建议：
        - 故障描述模糊时：stage1_k=30, stage2_k=15, final_k=5
        - 故障描述精确时：stage1_k=20, stage2_k=10, final_k=3
        """
        
        # ==========================================
        # Stage 0: 场景预过滤
        # ==========================================
        scenario_filtered_docs = self._filter_by_scenario(self.docs, current_scenario)
        
        if not scenario_filtered_docs:
            return f"未找到适用于场景 '{current_scenario}' 的故障诊断信息。"
        
        # 记录过滤后文档在原始 self.docs 中的索引（用于获取优先级权重）
        scenario_doc_indices = [i for i, doc in enumerate(self.docs) 
                                if doc in scenario_filtered_docs]
        
        print(f"[RAG] Stage 0: 场景过滤 - 从 {len(self.docs)} 个文档中筛选出 {len(scenario_filtered_docs)} 个适用于 '{current_scenario}' 的文档")
        
        # 为场景过滤后的文档重新构建临时 BM25 模型
        scenario_texts = [doc.page_content for doc in scenario_filtered_docs]
        scenario_tokenized = [jieba.lcut(text.lower()) for text in scenario_texts]
        scenario_bm25 = BM25Plus(scenario_tokenized)
        
        # ==========================================
        # Stage 1: 双路召回（扩大覆盖面）
        # ==========================================
        print(f"[RAG] Stage 1: 双路召回 - 目标各召回 {stage1_k} 个文档")
        
        # 路径 1: BM25 关键词召回
        tokenized_query = jieba.lcut(query.lower())
        bm25_scores = scenario_bm25.get_scores(tokenized_query)
        scored_bm25 = sorted(zip(scenario_filtered_docs, scenario_doc_indices, bm25_scores), 
                            key=lambda x: x[2], reverse=True)
        bm25_results = [(doc, idx) for doc, idx, score in scored_bm25 if score > 0][:stage1_k]
        
        # 路径 2: Milvus 向量召回
        query_vector = self.embeddings.embed_query(query)
        
        if current_scenario:
            filter_expr = f'applicable_scenarios like "%全场景%" or applicable_scenarios like "%{current_scenario}%"'
        else:
            filter_expr = None
        
        milvus_results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],      
            limit=stage1_k,  # 增加召回数量
            filter=filter_expr,
            output_fields=["text", "fault_name", "node_type", "applicable_scenarios"] 
        )
        
        milvus_docs_with_idx = []
        for hits in milvus_results:         
            for hit in hits:                
                entity = hit.get("entity")
                scenarios_str = entity.get("applicable_scenarios", "全场景")
                applicable_scenarios = [s.strip() for s in scenarios_str.split(",")]
                
                doc = Document(
                    page_content=entity.get("text"),
                    metadata={
                        "fault_name": entity.get("fault_name"),
                        "node_type": entity.get("node_type"),
                        "applicable_scenarios": applicable_scenarios
                    }
                )
                
                # 找到该文档在 self.docs 中的索引
                try:
                    idx = next(i for i, d in enumerate(self.docs) 
                              if d.page_content == doc.page_content)
                    milvus_docs_with_idx.append((doc, idx))
                except StopIteration:
                    # 如果找不到（理论上不应该发生），使用默认索引 0
                    milvus_docs_with_idx.append((doc, 0))
        
        print(f"[RAG] Stage 1 召回结果：BM25={len(bm25_results)} 个, Vector={len(milvus_docs_with_idx)} 个")
        
        # ==========================================
        # Stage 2: 快速预排（多样性保证 + 去重 + 层级先验）
        # ==========================================
        print(f"[RAG] Stage 2: 快速预排 - 目标筛选 {stage2_k} 个多样化候选")
        
        # 合并去重（按故障名称去重，保留最早出现的）
        unique_docs = {}
        unique_indices = {}
        for doc, idx in (bm25_results + milvus_docs_with_idx):
            fault_key = doc.metadata.get("fault_name", doc.page_content[:50])
            if fault_key not in unique_docs:
                unique_docs[fault_key] = doc
                unique_indices[fault_key] = idx
        
        candidate_docs = list(unique_docs.values())
        candidate_indices = [unique_indices[doc.metadata.get("fault_name", doc.page_content[:50])] 
                            for doc in candidate_docs]
        
        print(f"[RAG] 去重后候选文档数：{len(candidate_docs)} 个")
        
        if not candidate_docs:
            return f"检索系统未找到与该故障相关的信息（场景：{current_scenario}）。"
        
        # 快速预排：基于向量+BM25+层级权重的轻量级融合排序
        candidate_docs = self._fast_prerank(
            query=query, 
            query_vector=query_vector,
            docs=candidate_docs, 
            doc_indices=candidate_indices,
            bm25_model=scenario_bm25,
            top_k=min(stage2_k, len(candidate_docs))  # 防止候选数不足
        )
        
        print(f"[RAG] Stage 2 预排后候选数：{len(candidate_docs)} 个")
        
        # ==========================================
        # Stage 3: 交叉编码器精排（只对精选的候选进行重排）
        # ==========================================
        print(f"[RAG] Stage 3: 交叉编码器精排 - 处理 {len(candidate_docs)} 个文档")
        
        pairs = [[query, doc.page_content] for doc in candidate_docs]
        scores = self.cross_encoder.predict(pairs)
        
        scored_docs = sorted(zip(candidate_docs, scores), key=lambda x: x[1], reverse=True)
        
        # ==========================================
        # 自适应调整 final_k（根据分数分布动态决定返回数量）
        # ==========================================
        if enable_adaptive and len(scored_docs) > 1:
            # 计算分数的标准差和分数差距
            score_list = [score for _, score in scored_docs]
            top_score = score_list[0]
            
            # 策略 1: 如果 Top-1 分数显著高于其他（差距 > 0.5），说明故障明确
            if len(score_list) > 1 and (top_score - score_list[1]) > 0.5:
                adaptive_k = min(4, final_k)  # 返回少一点
                print(f"[RAG] 自适应调整：检测到高置信度故障，返回 {adaptive_k} 个结果")
            
            # 策略 2: 如果前 final_k 个分数都很接近（差距 < 0.2），说明多种故障都可能
            elif len(score_list) >= final_k:
                score_range = top_score - score_list[final_k - 1]
                if score_range < 0.2:
                    adaptive_k = min(final_k + 4, len(scored_docs))  # 多返回 5 个
                    print(f"[RAG] 自适应调整：检测到多种可能故障，返回 {adaptive_k} 个结果")
                else:
                    adaptive_k = final_k
            else:
                adaptive_k = final_k
        else:
            adaptive_k = final_k
        
        # ==========================================
        # 格式化输出（增加故障层级信息）
        # ==========================================
        final_result = ""
        for i, (doc, score) in enumerate(scored_docs[:adaptive_k]):
            fault_name = doc.metadata.get('fault_name', '未知故障')
            node_type = doc.metadata.get('node_type', '未知节点')
            scenarios = ", ".join(doc.metadata.get('applicable_scenarios', ['未知场景']))
            
            # 【新增】显示故障层级
            fault_level = get_fault_level_from_metadata(doc.metadata)
            priority = FAULT_LEVEL_PRIORITY.get(fault_level, 1.0)
            
            final_result += f"## 诊断知识 [{i+1}] 重排置信度: {score:.4f}\n"
            final_result += f"**故障类型**: {fault_name} | **节点类型**: {node_type} | **故障层级**: {fault_level} (优先级×{priority})\n"
            final_result += f"**适用场景**: {scenarios}\n"
            final_result += f"{doc.page_content}\n\n"
        
        return final_result.strip()

    def _drop_all_collections(self):
        """
        丢弃 Milvus 数据库中的全部 collection
        用于清理测试数据或重置数据库
        """
        collection_names = self.client.list_collections()
        if not collection_names:
            print("[Milvus] 当前数据库为空，没有需要删除的 collection。")
            return
        for name in collection_names:
            self.client.drop_collection(collection_name=name)
            print(f"[Milvus] 已成功删除 collection: {name}")


# ==========================================
# 第五部分：测试入口
# ==========================================
if __name__ == "__main__":
    # 第一次运行时设置 force_rebuild=True 以创建新的数据库表结构
    kb = FaultDiagnosisKnowledgeBase(force_rebuild=True)  # 首次运行改为 True，后续改为 False

    # 测试查询 1：链路层故障（应该被优先级加成）
    query = "网络通信很慢，不稳定"
    current_scenario = "static_routing"
    print(f"\n{'='*60}")
    print(f"[测试 Query 1]: {query}")
    print(f"[当前场景]: {current_scenario}")
    print(f"{'='*60}")
    result_text = kb.search(query, current_scenario=current_scenario)
    print(result_text)

    # 测试查询 2：BGP 故障（路由协议层优先级高）
    query = "bmv2 交换机总是丢弃数据包"
    current_scenario = "p4_star"
    print(f"\n{'='*60}")
    print(f"[测试 Query 2]: {query}")
    print(f"[当前场景]: {current_scenario}")
    print(f"{'='*60}")
    result_text = kb.search(query, current_scenario=current_scenario)
    print(result_text)

    # 测试查询 3：主机层故障（优先级基准）
    query = "大并发请求时，AI 服务突然无响应"
    current_scenario = "ai_inference"
    print(f"\n{'='*60}")
    print(f"[测试 Query 3]: {query}")
    print(f"[当前场景]: {current_scenario}")
    print(f"{'='*60}")
    result_text = kb.search(query, current_scenario=current_scenario)
    print(result_text)
