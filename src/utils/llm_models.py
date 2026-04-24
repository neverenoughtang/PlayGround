import os
from dotenv import load_dotenv
import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

load_dotenv()

def load_model(backend_model: str = "qwen3.6-medium") -> BaseChatModel:
    """
    统一使用 ChatOpenAI 接口加载大模型，完美兼容 LangGraph 和 MCP。
    """
    # 1. 实验室本地部署的开源大模型
    if backend_model in ["qwen3.6-big", "qwen3.6-medium"]:
        if backend_model[-1] == "g":
            URL = os.getenv("BIG_URL")
        elif backend_model[-1] == "m":
            URL = os.getenv("MIDIUM_URL")

        llm = ChatOpenAI(
            model="qwen3.6-35b-a3b",
            base_url=URL,
            api_key="any",
            temperature=0 # 排障任务必须为0，保证工具调用稳定性
        )
    # 2. Google Gemini 系列 (只能用来做文本推理，不可用于)
    elif backend_model in ["gemini-3-flash-preview"]:
        base_url = os.getenv("GEMINI_API_URL")
        proxy_url = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        http_client = httpx.Client(proxy=proxy_url) if proxy_url else None

        llm = ChatOpenAI(
            model=backend_model,
            base_url=base_url,
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
            timeout=20,
            http_client=http_client # 接管底层网络请求，确保能走通代理
        )
    else:
        raise ValueError(f"Unsupported backend model: {backend_model}")
        
    return llm

if __name__ == "__main__":
    # 本地测试代码
    try:
        gemini_llm = load_model("gemini-3-flash-preview")
        print("加载完成")
        print(gemini_llm.invoke([HumanMessage(content="你是谁？一句话回答。")]).content)
    except Exception as e:
        print(f"调用失败: {e}")