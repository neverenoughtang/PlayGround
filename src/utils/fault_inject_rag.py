import os       
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1" # No Proxy 提到前面

import warnings 
import logging
import subprocess # 【新增】用于执行 docker 命令
import time       # 【新增】用于等待容器启动
import socket     # 【新增】用于检测 Milvus 端口是否就绪
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 载入全局 .env
# ==========================================
# 第二部分：代理屏蔽与离线模式
# ==========================================
os.environ["HF_HUB_OFFLINE"] = "1"       # 告诉 huggingface_hub 库：别联网
os.environ["TRANSFORMERS_OFFLINE"] = "1"  # 告诉 transformers 库：别联网

# 【新增核心】：通过环境变量彻底关掉 HuggingFace Hub 底层可能的下载进度条
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
os.makedirs(MODEL_DIR, exist_ok=True) # 如果 rag_models 文件夹不存在，就自动创建；如果已存在，不报错（exist_ok=True）
os.environ["HF_HOME"] = MODEL_DIR # 告诉 HuggingFace：你的"家"在 MODEL_DIR，所有模型都去这里找
os.environ["HF_HUB_CACHE"] = MODEL_DIR # 告诉 HuggingFace Hub：缓存目录也在 MODEL_DIR
warnings.filterwarnings("ignore") # 屏蔽所有 Python 的 Warning 输出，让终端更干净

# ==========================================
# 第三部分：导入第三方库
# ==========================================
# 【新增核心】：强行通过 transformers 内部日志 API 禁用加载进度条！
# 这两行代码是专门用来杀掉 "Loading weights: 100%" 动画的
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
jieba.setLogLevel(logging.WARNING) # 【新增】：强制屏蔽 jieba 内部的构建字典提示

from .network_domain_words import DOMAIN_WORDS

# ==========================================
# 第四部分：核心类 FaultKnowledgeBase
# ==========================================
class FaultKnowledgeBase:
    """
    故障注入知识库：一个完整的 RAG 系统
    
    建库流程 (首次或 force_rebuild=True)：
    1. 读取 Markdown 故障手册 
    2. 按标题切分成小块 
    3. 每块用 BGE-M3 生成向量，用 Jieba 切分成 token 列表
    4. 把 向量 + 原文 + 故障名称元数据 + 切分结果(tokenized_text) 存进 Milvus 数据库
    
    日常加载流程 (数据库已存在)：
    1. 瞬间从 Milvus 拉取所有 text 与 tokenized_text。
    2. 在内存中还原 docs 列表与 BM25Plus 模型，跳过重构开销。

    查询流程：
    1. 用户提问 
    2. BM25Plus 关键词检索（路1）+ Milvus 向量检索（路2）
    3. 合并去重 
    4. CrossEncoder 重排精选 
    5. 返回最相关的文档给大模型
    """
    
    def __init__(self, 
                 md_path: str = DOC_DIR,            
                 db_uri: str = os.getenv("MILVUS_URI", "http://127.0.0.1:19530"),  
                 collection_name: str = "fault_inject",  # 集合名
                 force_rebuild: bool = False):      # 是否强制重建数据库
        
        # ----- 1. 确定文件路径 -----
        self.md_path = os.path.join(md_path, "fault_inject.md")
        self.db_uri = db_uri                    # 保存数据库连接地址
        self.collection_name = collection_name  # 保存集合名
        self._ensure_milvus_running() # 在加载模型和连接数据库之前，先唤醒沉睡的容器

        # ----- 2. 加载 Embedding 模型（向量化模型）-----
        # print("[RAG] 正在加载 BGE-M3 向量化模型...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",            # 模型名称：北京智源的 BGE-M3，支持中英文，1024维输出
            model_kwargs={'device': 'cpu'},      # 用 CPU 推理（没有 GPU 或 GPU 不够时的选择）
            encode_kwargs={'normalize_embeddings': True}  # 输出向量做 L2 归一化（长度变为1）
        )
        self.embedding_dim = 1024  # BGE-M3 模型输出的向量维度是 1024

        # ----- 3. 加载 Reranker 模型（重排模型）-----
        # print("[RAG] 正在加载 BGE-Reranker-v2-M3 重排模型...")
        self.cross_encoder = CrossEncoder(
            model_name_or_path="BAAI/bge-reranker-v2-m3",  # 北京智源的重排模型，专门给文档相关性打分
            device="cpu",       # 用 CPU 推理
            max_length=1024     # 输入文本最大长度（超过会被截断）
        )
        
        # ----- 4. 热加载预热 NLP 分词引擎 -----
        self._init_nlp()
        
        # ----- 5. 连接 Milvus 数据库并初始化 -----
        self.docs = []  # 初始化空列表，不论是从 MD 解析还是从 DB 拉取，最终都在这
        # print(f"[RAG] 正在连接企业级 Milvus 数据库 ({self.db_uri})...")
        self.client = MilvusClient(uri=self.db_uri)
        
        # 调用智能初始化方法：判断是建新表还是读取旧表恢复数据
        self._smart_init_milvus(force_rebuild) 

    def _init_nlp(self):
        """
        一次性将网络领域黑话词典加载进内存，避免运行时冷启动开销
        """
        # print("[RAG] 正在预热 jieba NLP 模型与专有名词库...")
        for word in DOMAIN_WORDS:
            jieba.add_word(word)
        # 强行切分一个词，触发 jieba 内部大字典的懒加载机制
        _ = jieba.lcut("故障注入引擎热加载完成")
        # print("[RAG] NLP 模型预热完成！")

    def _ensure_milvus_running(self):
        """
        Docker 状态检查与自启守护
        """
        # print("[RAG] 正在检查 Milvus 底层容器状态...")
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", "milvus-standalone"],
                capture_output=True, text=True
            )
            if "true" not in result.stdout.lower():
                # print("[RAG] 发现 Milvus 容器组未运行，正在自动唤醒...")
                subprocess.run(
                    ["docker", "start", "milvus-etcd", "milvus-minio", "milvus-standalone"], 
                    check=True
                )
                # print("[RAG] 容器组已拉起，正在等待 19530 端口服务就绪...")
                port_ready = False

                # 轮询探测端口 (polling)
                for i in range(20):
                    try:
                        with socket.create_connection(("127.0.0.1", 19530), timeout=1):
                            port_ready = True
                            # print("[RAG] 端口 19530 通信握手成功，Milvus 服务已完全就绪！")
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

    def _load_and_split_docs(self):
        """
        【文档切分 + 上下文增强】
        此处仅在 force_rebuild=True 或首次建库时被调用
        """
        # print("[RAG] 正在读取本地 Markdown 文档并进行语义切块...")
        with open(self.md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        headers_to_split_on = [("#", "fault_name")] 
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        raw_docs = markdown_splitter.split_text(md_content)

        # 【上下文增强：把标题信息注入正文】
        for doc in raw_docs:
            fault_name = doc.metadata.get("fault_name", "")
            if fault_name and fault_name not in doc.page_content:
                doc.page_content = f"【关联故障：{fault_name}】\n{doc.page_content}"
            self.docs.append(doc) 

    def _smart_init_milvus(self, force_rebuild: bool):
        """
        Milvus 数据库智能初始化 (含全新建库逻辑)
        - 若集合存在且不要求重建：直接从 Milvus 提取预先处理好的原文和 tokenized_text 还原内存环境。
        - 若集合不存在或要求重建：走重新解析文件 -> 构筑 Schema -> 切词向量化落库的完整流程。
        """
        if self.client.has_collection(collection_name=self.collection_name):
            if force_rebuild:
                print(f"[RAG] 收到强制重建指令，正在摧毁旧集合 '{self.collection_name}'...")
                
                # # 👇👇👇 【重点提示】这是由于表结构变更，DROP 旧页表结构的代码行！👇👇👇
                self.client.drop_collection(collection_name=self.collection_name)
                # # 👆👆👆 如果你想测试主函数，确保 force_rebuild=True 就能顺利走到这里 👆👆👆
                
            else:
                # 【架构升级】不重建时，彻底抛弃本地 MD 读取，直接用数据库做全量内存还原！
                print(f"[RAG] 检测到集合 '{self.collection_name}' 已存在且未要求重建，准备从数据库热加载！")
                self.client.load_collection(collection_name=self.collection_name)
                
                print("[RAG] 正在从 Milvus 读取并恢复所有历史原文与 NLP 分词缓存...")
                # 通过 filter id >= 0 拉取全量实体 (Milvus auto_id 生成的数字均为正数)
                results = self.client.query(
                    collection_name=self.collection_name,
                    filter="id >= 0", 
                    output_fields=["text", "fault_name", "tokenized_text"]
                )
                
                # 开始在内存中还原 self.docs 和 self.bm25_model
                tokenized_corpus = []
                for row in results:
                    self.docs.append(Document(
                        page_content=row["text"], 
                        metadata={"fault_name": row["fault_name"]}
                    ))
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
        
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False) 
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="fault_name", datatype=DataType.VARCHAR, max_length=1024)
        # 【新增 Schema 字段】：空间换时间的核心，持久化存储 jieba 分词结果
        schema.add_field(field_name="tokenized_text", datatype=DataType.VARCHAR, max_length=65535)
        
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", metric_type="COSINE", index_type="AUTOINDEX")
        
        self.client.create_collection(
            collection_name=self.collection_name, 
            schema=schema, 
            index_params=index_params 
        )
        
        # 调用写入逻辑
        self._insert_docs_to_milvus()

    def _insert_docs_to_milvus(self):
        """
        把文档向量化、词频化并写入 Milvus 数据库
        """
        # print(f"[RAG] 正在生成语义向量与词元划分，并全量同步到 Milvus...")
        
        texts = [doc.page_content for doc in self.docs]
        
        # 1. 批量生成 1024 维密集语义向量
        vectors = self.embeddings.embed_documents(texts)
        
        # 2. 【新增】：执行写时分词，一并将二维切分结果保存在类中，顺手构造初始的 BM25Plus 模型
        tokenized_corpus = [jieba.lcut(text.lower()) for text in texts]
        self.bm25_model = BM25Plus(tokenized_corpus)
        
        # 3. 数据打包落库
        data = []
        for doc, vector, tokens in zip(self.docs, vectors, tokenized_corpus):
            data.append({
                "vector": vector,                                     # 1024 维浮点数组
                "text": doc.page_content,                             # 原始文本
                "fault_name": doc.metadata.get("fault_name", "未知"),  # 元数据
                "tokenized_text": " ".join(tokens)                    # 将分词结果用空格拼接，持久化写入数据库
            })
            
        self.client.insert(collection_name=self.collection_name, data=data)
        self.client.load_collection(collection_name=self.collection_name)
        print("[RAG] 数据库首次同步写入彻底完成！")

    def search(self, query: str, ensemble_k: int = 10, final_k: int = 2) -> str:
        """
        双路召回 + 重排 的核心搜索方法
        """
        # ==========================================
        # 【召回路 1】BM25Plus 稀疏检索（中文优化版关键词精准匹配）
        # ==========================================
        # 针对用户的 query 临时执行极速切分
        tokenized_query = jieba.lcut(query.lower())
        
        # 利用由数据库或初始化建立好的模型内存极速算分
        bm25_scores = self.bm25_model.get_scores(tokenized_query)
        
        # 将文档和得分绑定并倒序排列
        scored_bm25 = sorted(zip(self.docs, bm25_scores), key=lambda x: x[1], reverse=True)
        
        # 提取前 ensemble_k 个有效文档 (过滤掉彻底无关的 0 分项)
        bm25_docs = [doc for doc, score in scored_bm25 if score > 0][:ensemble_k]
        
        # ==========================================
        # 【召回路 2】Milvus 稠密向量检索（语义模糊匹配）
        # ==========================================
        query_vector = self.embeddings.embed_query(query)
        
        milvus_results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],      
            limit=ensemble_k,         
            output_fields=["text", "fault_name"] 
        )
        
        milvus_docs = []
        for hits in milvus_results:         
            for hit in hits:                
                entity = hit.get("entity")  
                milvus_docs.append(Document(
                    page_content=entity.get("text"),                      
                    metadata={"fault_name": entity.get("fault_name")}     
                ))
        
        # 合并去重
        unique_docs = {doc.page_content: doc for doc in (bm25_docs + milvus_docs)}
        candidate_docs = list(unique_docs.values())
        
        if not candidate_docs:
            return "检索系统未找到与该故障相关的信息。"

        # ==========================================
        # 【交叉重排（Reranking）】
        # ==========================================
        # 交叉验证，依据相关性分数排序
        pairs = [[query, doc.page_content] for doc in candidate_docs]
        scores = self.cross_encoder.predict(pairs)
        
        scored_docs = sorted(zip(candidate_docs, scores), key=lambda x: x[1], reverse=True)
        
        # 取 Top-K 结果，格式化输出
        final_result = ""
        for i, (doc, score) in enumerate(scored_docs[:final_k]):
            final_result += f"## 匹配结果 [{i+1}] 重排置信度得分: {score:.4f} (故障名称: {doc.metadata.get('fault_name', '未知')})\n"
            final_result += f"{doc.page_content}\n\n"
            
        return final_result.strip()

    def _drop_all_collections(self):
        """丢弃 Milvus 数据库中的全部 collection。"""
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
    # 既然表结构变了，第一次测试时将 force_rebuild=True 激活即可走到重建逻辑
    kb = FaultKnowledgeBase(force_rebuild=True) 

    query = "默认路由有问题"
    print(f"\n[测试 Query]: {query}")
    print("正在执行领域词加强混合检索 + 交叉重排，请稍候...\n")
    result_text = kb.search(query)

    print("============== 最终发给 Agent 的内容 ==============")
    print(result_text)

    query = "通信很不稳定！"
    print(f"\n[测试 Query]: {query}")
    print("正在执行领域词加强混合检索 + 交叉重排，请稍候...\n")
    result_text = kb.search(query)

    print("============== 最终发给 Agent 的内容 ==============")
    print(result_text)