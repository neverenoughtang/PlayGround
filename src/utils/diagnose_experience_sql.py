import os
import socket
import subprocess
import time
import pymysql
import asyncio
from typing import List
import jieba
# 新增：屏蔽 Python 3.12 对 jieba 源码产生的 SyntaxWarning 警告
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning) 
import jieba
from rank_bm25 import BM25Plus  # 将 BM25Okapi 换成 BM25Plus，避免分数为负数

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) # 载入全局 .env

from .network_domain_words import DOMAIN_WORDS

class DiagnoseExperienceBase:
    """
    故障诊断经验库：一个完整的 SQL 数据库
    
    建库流程：
    1. 建立连接
    2. 创建表结构 (包含 lab_name 索引优化查询速度)

    功能：
    1. 增加一条成功经验
    2. 删除某条指定 ID 的经验
    3. 根据当前网络场景（精确）和用户投诉表现（模糊）查询几条经验
    4. 清空经验库
    """
    def __init__(self):
        # ---------------------------------------------------------
        # 数据库连接配置 (根据 Docker 部署的参数进行设置)
        # ---------------------------------------------------------
        self.db_host = os.getenv("MYSQL_HOST", "127.0.0.1") # 数据库 IP
        self.db_port = int(os.getenv("MYSQL_PORT", 3306))   # 端口
        self.db_user = os.getenv("MYSQL_USER", "root")      # 用户名
        self.db_pass = os.getenv("MYSQL_PASSWORD", "Root@123456") # 密码
        self.db_name = os.getenv("MYSQL_DB", "agent_memory_db")   # 数据库名

        # 0. 检查并拉起 MySQL Docker 容器
        self._ensure_mysql_running()

        # 1. 初始化数据库表结构
        self._init_db()

        # 2. 预热 jieba NLP 模型
        self._init_nlp() 

    def _ensure_mysql_running(self):
        """
        Docker 状态检查与自启守护 (MySQL)
        """
        print("⏳ [Summary Agent] 正在检查 MySQL 底层容器及端口状态...")
        port_ready = False
        try:
            with socket.create_connection((self.db_host, self.db_port), timeout=1):
                port_ready = True
        except OSError:
            pass

        if port_ready:
            print("✅ [Summary Agent] MySQL 端口(3306)通信握手成功，服务运行正常。")
            return

        print("⚠️ [Summary Agent] 发现 MySQL 端口未就绪，尝试自动唤醒 mysql 容器...")
        try:
            # 👇 【核心修复】：将容器名改为 diagnosis-mysql
            container_name = "diagnosis-mysql" 
            
            result = subprocess.run(["docker", "start", container_name], check=False, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ [Summary Agent] Docker 启动命令执行失败，错误信息: {result.stderr.strip()}")
            else:
                print("⏳ [Summary Agent] 容器启动指令已发送，等待端口服务就绪...")

            for i in range(20):
                try:
                    with socket.create_connection((self.db_host, self.db_port), timeout=1):
                        port_ready = True
                        print("✅ [Summary Agent] MySQL 服务已完全就绪！")
                        break
                except OSError:
                    import time
                    time.sleep(1)
                    print(f"  ... 内部服务初始化中 ({i+1}/20)")
            if not port_ready:
                print("❌ [Summary Agent] 警告：等待 MySQL 端口就绪超时，接下来的连接可能会失败。")
        except Exception as e:
            print(f"❌ [Summary Agent] 启动 Docker 容器时发生异常: {e}")

    def _init_nlp(self):
        """
        【效率优化点 1：解决冷启动】
        在类实例化时，一次性把自定义领域词典加载进内存，并触发 jieba 的懒加载构建前缀树。
        这样可以把 0.75s 的耗时转移到系统启动阶段，让用户的 Search 实时响应。
        """
        print("⏳ [Summary Agent] 正在预热 NLP 模型与专有名词库...")
        domain_words = DOMAIN_WORDS
        for word in domain_words:
            jieba.add_word(word)

        # 强行切分一个词，触发 jieba 内部懒加载读取 /tmp/jieba.cache
        _ = jieba.lcut("网络故障诊断预热完成")
        print("✅ [Summary Agent] NLP 模型预热完成！")

    def _init_db(self):
        """
        初始化表结构。
        注意：新增了 complaint_tokens 字段用于空间换时间。
        """
        try:
            connection = pymysql.connect(
                host=self.db_host,
                port=self.db_port,
                user=self.db_user,
                password=self.db_pass,
                database=self.db_name,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            
            with connection.cursor() as cursor:
                # # ⭐ 先强制删除旧的表结构（仅限开发阶段使用，生产环境请用 ALTER TABLE 加字段）
                # cursor.execute("DROP TABLE IF EXISTS successful_cases;")

                # 增加 INDEX idx_lab_name，极大加速精确匹配 lab_name 的查询速度
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS successful_cases (
                    id INT AUTO_INCREMENT PRIMARY KEY, -- 递增 ID 作为主键
                    lab_name VARCHAR(50) NOT NULL,     -- 拓扑场景名
                    fuzzy_complaint TEXT NOT NULL,     -- 模糊投诉表象
                    root_cause VARCHAR(100) NOT NULL,  -- 最终查出的根本原因
                    key_actions TEXT NOT NULL,         -- 总结的排查动作捷径
                    complaint_tokens TEXT NOT NULL,    -- 【效率优化点2】: 新增字段，存储写时分词结果
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 时间戳
                    INDEX idx_lab_name (lab_name)      -- 为 lab_name 建立 B-Tree 索引
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                cursor.execute(create_table_sql)
            
            connection.commit() # 提交 DB 建立表结构
            print("✅ [Summary Agent] 数据库表结构初始化/检查完成。")
            
        except Exception as e:
            print(f"❌ [Summary Agent] 数据库连接或初始化失败: {e}")
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    async def insert_case(self, lab_name: str, fuzzy_complaint: str, root_cause: str, key_actions: str):
        """
        【写时分词】
        将经验进行分词，再写入数据库，提升效率
        """
        print("💾 [Summary Agent] 正在将经验持久化至 MySQL...")
        
        # 【效率优化点 2：空间换时间（写时分词）】
        # 在数据写入数据库前，提前切好词，统一转小写，并用空格拼接成字符串存入数据库。
        # 以后无论查多少次，这条记录都不需要重新参与 jieba 切分了。
        tokenized_list = jieba.lcut(fuzzy_complaint.lower())
        complaint_tokens = " ".join(tokenized_list)

        try:
            # 建立连接
            connection = pymysql.connect(
                host=self.db_host, port=self.db_port, user=self.db_user,
                password=self.db_pass, database=self.db_name, charset='utf8mb4'
            )
            # 执行插入SQL指令(打开事务)
            with connection.cursor() as cursor:
                insert_sql = """
                INSERT INTO successful_cases (lab_name, fuzzy_complaint, root_cause, key_actions, complaint_tokens)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (lab_name, fuzzy_complaint, root_cause, key_actions, complaint_tokens))
            # 提交
            connection.commit() # 持久性(Durability)

            print("🎉 [Summary Agent] 成功将本次排障经验录入 MySQL 经验池！")
            return True
            
        except Exception as e:
            print(f"❌ [Summary Agent] 数据库写入失败: {e}")
            # 【新增】如果失败, 将会回滚(原子性, Atomicity)
            connection.rollback() 
            return False
        finally:
            if 'connection' in locals() and connection.open:
                connection.close() # 关闭连接

    async def search(self, lab_name: str, keyword: str, limit: int = 10) -> str:
        """
        极速经验查询：精确匹配 lab_name，模糊匹配 fuzzy_complaint，返回 root_cause 不重复的结构化字符串。
        命中缓存后，彻底告别 DB I/O 与语料库分词开销。

        Args:
            lab_name: 拓扑场景名称 (利用索引，极速过滤)
            keyword: 用户输入的模糊投诉词
            limit: 最终保留的不重复 root_cause 数量
        
        Returns:
            response: 拼接好的 prompt 字符串，可直接喂给 agent
        """
        print(f"🔍 [Summary Agent] 正在查询场景 '{lab_name}' 下，关于 '{keyword}' 的历史排障经验(BM25)...")
        
        try:
            # 1. 查库获取该场景下所有记录及预分词结果
            connection = pymysql.connect(
                host=self.db_host, port=self.db_port, user=self.db_user,
                password=self.db_pass, database=self.db_name, charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            with connection.cursor() as cursor:
                query_sql = """
                SELECT id, fuzzy_complaint, root_cause, key_actions, complaint_tokens
                FROM successful_cases 
                WHERE lab_name = %s
                ORDER BY created_at DESC
                """
                cursor.execute(query_sql, (lab_name,))
                results = cursor.fetchall()

            if not results:
                return "暂无相关历史经验可供参考。"

            # 2. 从记录中提取预分词的 token 列表
            tokenized_corpus = [row['complaint_tokens'].split(" ") for row in results]
            
            # 3. 实时构建 BM25Plus 模型 (因为跳过了 jieba 分词，仅做数学统计，速度极快)
            bm25 = BM25Plus(tokenized_corpus)

            # 4. 对用户的 query 这一句话进行实时分词
            tokenized_query = jieba.lcut(keyword.lower())
            
            # 5. 计算得分与排序
            doc_scores = bm25.get_scores(tokenized_query)
            scored_results = sorted(zip(results, doc_scores), key=lambda x: x[1], reverse=True)

            # 6. 过滤去重
            seen_root_causes = set()
            unique_cases = []
            
            for row, score in scored_results:
                if score <= 0:
                    continue
                rc = row['root_cause']
                if rc not in seen_root_causes:
                    seen_root_causes.add(rc)
                    unique_cases.append(row)
                if len(unique_cases) >= limit:
                    break
            
            if not unique_cases:
                return "当前场景下，未能检索到与该投诉表象高度相关的历史经验。"

            # 7. 组装输出
            memory_str = f"【历史相关排障经验参考 (场景: {lab_name})】\n"
            for idx, case in enumerate(unique_cases, 1):
                memory_str += f"--- 经验 Case {idx} ---\n"
                memory_str += f"- 历史现象: {case['fuzzy_complaint']}\n"
                memory_str += f"- 根本原因 (Root Cause): {case['root_cause']}\n"
                memory_str += f"- 关键排查路径:\n{case['key_actions'].strip()}\n\n"
            
            return memory_str

        except Exception as e:
            print(f"❌ [Summary Agent] BM25 检索失败: {e}")
            return "提取历史经验时发生内部检索错误。"
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()
            
    async def print_all_cases(self):
        """
        打印经验库中的所有记录
        """
        print("🖨️ [Summary Agent] 正在打印所有排障经验记录...")
        try:
            connection = pymysql.connect(
                host=self.db_host, port=self.db_port, user=self.db_user,
                password=self.db_pass, database=self.db_name, charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM successful_cases ORDER BY id ASC")
                results = cursor.fetchall()
            
            if not results:
                print("⚠️ 当前经验库为空。")
                return

            print(f"共找到 {len(results)} 条记录：\n" + "="*40)
            for row in results:
                print(f"【ID: {row['id']}】 场景: {row['lab_name']} | 根因: {row['root_cause']}")
                print(f"现象: {row['fuzzy_complaint']}")
                print(f"动作:\n{row['key_actions'].strip()}\n" + "-"*40)
                
        except Exception as e:
            print(f"❌ [Summary Agent] 打印记录失败: {e}")
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    async def delete_case_by_id(self, case_id: int) -> bool:
        """
        根据指定的 ID 删除单条经验记录。
        """
        print(f"🗑️ [Summary Agent] 准备删除 ID 为 {case_id} 的经验记录...")
        try:
            connection = pymysql.connect(
                host=self.db_host, port=self.db_port, user=self.db_user,
                password=self.db_pass, database=self.db_name, charset='utf8mb4'
            )
            with connection.cursor() as cursor:
                delete_sql = "DELETE FROM successful_cases WHERE id = %s"
                cursor.execute(delete_sql, (case_id,))
            
            connection.commit()
            print(f"✅ [Summary Agent] 成功删除 ID 为 {case_id} 的记录。")
            return True
            
        except Exception as e:
            print(f"❌ [Summary Agent] 删除记录失败: {e}")
            # 【新增】如果失败, 将会回滚(原子性, Atomicity)
            connection.rollback()             
            return False
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()

    async def clear_all_cases(self) -> bool:
        """
        清空经验库中的所有记录，并重置自增 ID。
        """
        print("⚠️ [Summary Agent] 警告：正在清空所有排障经验记录...")
        try:
            connection = pymysql.connect(
                host=self.db_host, port=self.db_port, user=self.db_user,
                password=self.db_pass, database=self.db_name, charset='utf8mb4'
            )
            with connection.cursor() as cursor:
                truncate_sql = "TRUNCATE TABLE successful_cases"
                cursor.execute(truncate_sql)
            
            connection.commit()
            print("✅ [Summary Agent] 经验库已全部清空，ID 计数已重置。")
            return True
            
        except Exception as e:
            print(f"❌ [Summary Agent] 清空经验库失败: {e}")
            return False
        finally:
            if 'connection' in locals() and connection.open:
                connection.close()


# ==========================================
# 本地测试代码 (直接运行本文件即可测试)
# ==========================================
if __name__ == "__main__":
    async def test():
        # 注意：__init__ 未定义 backend_model，这里去掉无效参数
        DB = DiagnoseExperienceBase()
        
        # 1. 打印全部case
        await DB.print_all_cases()

        # # 2. 查询 1 次 Case
        # # 精确查询 ospf_enterprise，模糊查询包含 "彻底断网" 的记录
        # query_result = await DB.search(
        #     lab_name="ospf_enterprise", 
        #     keyword="断网", 
        #     limit=10
        # )
        # print("\n👇 返回给 Agent 的 System Prompt 补充内容：\n")
        # print(query_result)
        # print("="*40)

        # # 3. 清空
        # # 测试结束后，恢复数据库原状 (可选)
        # await DB.clear_all_cases()

    # 运行异步测试主函数
    asyncio.run(test())