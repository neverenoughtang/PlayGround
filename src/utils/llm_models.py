import os
from dotenv import load_dotenv
import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

load_dotenv()

def load_model(backend_model: str = "qwen3.5-small") -> BaseChatModel:
    """
    统一使用 ChatOpenAI 接口加载大模型，完美兼容 LangGraph 和 MCP。
    """
    # 1. 实验室本地部署的开源大模型
    if backend_model in ["qwen3.5-big", "qwen3.5-medium", "qwen3.5-small"]:
        if backend_model[-1] == "g":
            URL = os.getenv("BIG_URL")
        elif backend_model[-1] == "m":
            URL = os.getenv("MIDIUM_URL")
        elif backend_model[-1] == "l":
            URL = os.getenv("SMALL_URL")

        llm = ChatOpenAI(
            model="qwen3.6-35b-a3b",
            base_url=URL,
            api_key="any",
            temperature=0 # 排障任务必须为0，保证工具调用稳定性
        )
    # 2. Google Gemini 系列 (使用最新的 OpenAI 兼容接口)
    elif backend_model in ["gemini-3-flash-preview"]:
        # 💡 诊断检查点 1: 确保基础 URL 格式正确
        # Google 的 OpenAI 兼容接口，URL 必须以 /openai/ 结尾
        # 正确示例: https://generativelanguage.googleapis.com/v1beta/openai/
        base_url = os.getenv("GEMINI_API_URL")
        
        # 💡 诊断检查点 2: 配置显式代理
        # 如果你绕过了失效的 Nginx，但本地网络仍需代理才能访问外网，必须显式传入
        # 假设你本地有 Clash/V2ray 代理，例如：http://127.0.0.1:7890
        proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        http_client = httpx.Client(proxy=proxy_url) if proxy_url else None

        llm = ChatOpenAI(
            model=backend_model,
            base_url=base_url,
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
            timeout=20, # 👈 关键修复：设置超时，拒绝无限卡死！
            http_client=http_client # 👈 关键修复：接管底层网络请求，确保能走通代理
        )
    else:
        raise ValueError(f"Unsupported backend model: {backend_model}")
        
    return llm

if __name__ == "__main__":
    # 本地测试代码
    try:
        # 测试 Gemini
        gemini_llm = load_model("qwen3.5-small")
        print("加载完成")
        print(gemini_llm.invoke([HumanMessage(content="你是谁？一句话回答。")]).content)
    except Exception as e:
        print(f"调用失败: {e}")