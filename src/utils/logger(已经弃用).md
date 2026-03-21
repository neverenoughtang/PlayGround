import logging
import os
import sys
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# 定位到 PlayGround 根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 基础系统日志器
system_logger = logging.getLogger("PlayGround")
system_logger.setLevel(logging.INFO)
system_logger.propagate = False

if not system_logger.handlers:
    # 1. 全部输出到系统标准终端 (这是关键，app.py 将全局捕获它)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    system_logger.addHandler(sh)
    
    # 2. 全局日志文件记录 (保留)
    global_log_path = os.path.join(BASE_DIR, "runtime", "system.log")
    os.makedirs(os.path.dirname(global_log_path), exist_ok=True)
    fh = logging.FileHandler(global_log_path, encoding="utf-8", mode="a")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    system_logger.addHandler(fh)

def attach_case_log(lab_name: str, fault_name: str):
    """为当前测试用例动态添加专属的文件日志记录器"""
    log_dir = os.path.join(BASE_DIR, "runtime", "cases")
    os.makedirs(log_dir, exist_ok=True)
    
    case_log_path = os.path.join(log_dir, f"{lab_name}_{fault_name}.log")
    case_handler = logging.FileHandler(case_log_path, encoding="utf-8", mode="a")
    case_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    
    system_logger.addHandler(case_handler)
    return case_handler

def detach_case_log(handler):
    """安全地卸载专属日志记录器"""
    if handler in system_logger.handlers:
        system_logger.removeHandler(handler)
        handler.close()