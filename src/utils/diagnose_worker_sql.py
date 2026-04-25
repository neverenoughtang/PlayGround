# src/utils/diagnose_worker_sql.py
import os
import socket
import subprocess
import time
import pymysql
import asyncio

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 载入全局 .env

class DiagnoseWorkerKnowledgeBase:
    """
    【Worker 故障诊断专属知识库】
    面向对象设计。负责连接 MySQL，初始化数据库与表格，并将 Markdown 故障字典映射入库。
    提供异步查询接口供 Worker 节点在运行时直接调用。
    """
    _instance = None

    # 单例模式，确保整个系统生命周期内只实例化一次，避免连接池爆炸
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DiagnoseWorkerKnowledgeBase, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止单例被多次初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        # ---------------------------------------------------------
        # 1. 数据库连接配置 (兼容环境变量)
        # ---------------------------------------------------------
        self.db_host = os.getenv("MYSQL_HOST", "127.0.0.1")       # 数据库 IP
        self.db_port = int(os.getenv("MYSQL_PORT", 3306))         # 端口
        self.db_user = os.getenv("MYSQL_USER", "root")            # 用户名
        self.db_pass = os.getenv("MYSQL_PASSWORD", "Root@123456") # 密码
        self.db_name = os.getenv("MYSQL_DB", "agent_memory_db")   # 数据库名

        # ---------------------------------------------------------
        # 2. 系统启动自检与初始化
        # ---------------------------------------------------------
        # 0. 检查并拉起 MySQL Docker 容器
        self._ensure_mysql_running()
        # 1. 初始化数据库与表结构
        self._init_db()
        
        self._initialized = True

    def _ensure_mysql_running(self):
        """
        【健康检查】
        Docker 状态检查与自启守护。轮询测试 MySQL 端口。
        """
        port_ready = False
        try:
            with socket.create_connection((self.db_host, self.db_port), timeout=1):
                port_ready = True
        except OSError:
            pass

        if port_ready:
            return

        print("⚠️ [Worker DB] 发现 MySQL 端口未就绪，尝试自动唤醒 diagnosis-mysql 容器...")
        try:
            container_name = "diagnosis-mysql" 
            result = subprocess.run(["docker", "start", container_name], check=False, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ [Worker DB] Docker 启动命令执行失败: {result.stderr.strip()}")
            else:
                print("⏳ [Worker DB] 容器启动指令已发送，等待端口服务就绪...")

            # 轮询等待 20 秒
            for i in range(20):
                try:
                    with socket.create_connection((self.db_host, self.db_port), timeout=1):
                        port_ready = True
                        print("✅ [Worker DB] MySQL 服务已完全就绪！")
                        break
                except OSError:
                    time.sleep(1)
            
            if not port_ready:
                print("❌ [Worker DB] 警告：等待 MySQL 端口就绪超时，接下来的连接可能会失败。")
        except Exception as e:
            print(f"❌ [Worker DB] 启动 Docker 容器时发生异常: {e}")

    def _get_connection(self, include_db=True):
        """获取 MySQL 同步连接对象"""
        config = {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_pass,
            "charset": "utf8mb4"
        }
        if include_db:
            config["database"] = self.db_name
        return pymysql.connect(**config)

    def _init_db(self):
        """
        【库表初始化】
        创建数据库以及 diagnose_worker 表。
        """
        # 1. 创建数据库
        try:
            conn = self._get_connection(include_db=False)
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ [Worker DB] 创建数据库失败: {e}")

        # 2. 创建故障知识表 (使用 fault_name 作为主键)
        try:
            conn = self._get_connection(include_db=True)
            with conn.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS diagnose_worker (
                    fault_name VARCHAR(100) PRIMARY KEY COMMENT '故障英文名',
                    content LONGTEXT NOT NULL COMMENT '诊断排查知识点(Markdown)'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Worker诊断知识库';
                """
                cursor.execute(create_table_sql)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ [Worker DB] 创建 diagnose_worker 表失败: {e}")

    def load_markdown_to_db(self, md_file_path: str):
        """
        【知识注入】
        读取 md 文件并解析，以 '# 故障名' 为依据切块存入数据库。
        """
        if not os.path.exists(md_file_path):
            print(f"❌ [Worker DB] 找不到知识库文件: {md_file_path}")
            return

        with open(md_file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        blocks = md_content.split("\n# ")
        insert_count = 0
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                for block in blocks:
                    block = block.strip()
                    if not block: continue
                    
                    if block.startswith("# "): 
                        block = block[2:]

                    lines = block.split("\n", 1)
                    fault_name = lines[0].strip()
                    fault_content = lines[1].strip() if len(lines) > 1 else "无内容"

                    # 存在则覆盖更新 (ON DUPLICATE KEY UPDATE)
                    upsert_sql = """
                    INSERT INTO diagnose_worker (fault_name, content) 
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE content = VALUES(content);
                    """
                    cursor.execute(upsert_sql, (fault_name, fault_content))
                    insert_count += 1
            conn.commit()
            conn.close()
            print(f"📦 [Worker DB] 成功导入/更新 {insert_count} 条 Worker 诊断知识。")
        except Exception as e:
            print(f"❌ [Worker DB] 导入数据失败: {e}")

    async def query_fault_knowledge(self, fault_name: str) -> str:
        """
        【异步知识查询】
        Worker 唤醒时调用此接口，根据故障名获取对应的 Markdown 诊断指南。
        使用 asyncio.to_thread 防止阻塞主事件循环。
        """
        def _sync_query():
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    sql = "SELECT content FROM diagnose_worker WHERE fault_name = %s LIMIT 1"
                    cursor.execute(sql, (fault_name,))
                    result = cursor.fetchone()
                conn.close()
                return result[0] if result else None
            except Exception as e:
                print(f"⚠️ [Worker DB] 查询故障 '{fault_name}' 失败: {e}")
                return None

        # 将同步的 MySQL 查询抛入异步线程池
        return await asyncio.to_thread(_sync_query)


# ==========================================
# 🧪 本地测试入口
# ==========================================
if __name__ == "__main__":
    async def main_test():
        print("--- 开始测试 Worker MySQL 知识库 ---")
        kb = DiagnoseWorkerKnowledgeBase()
        
        # 测试加载 MD 文件 (请确保路径正确)
        target_md = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "utils", "docs", "fault_diagnose.md"))
        kb.load_markdown_to_db(target_md)
        
        print("\n--- 测试异步查询 ---")
        # 测试你最新改版后
        res = await kb.query_fault_knowledge("link_loss")
        if res:
            print(f"✅ 查询成功！内容截取:\n{res}")
        else:
            print("❌ 未查到数据。")

    asyncio.run(main_test())