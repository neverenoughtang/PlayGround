import os
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

load_dotenv()

def load_model(backend_model: str = "gemini-3-flash-preview") -> BaseChatModel:
    """
    统一使用 ChatOpenAI 接口加载大模型，完美兼容 LangGraph 和 MCP。
    """
    # 1. 实验室本地/云端部署的开源大模型
    if backend_model in ["qwen3.5-27b"]:
        llm = ChatOpenAI(
            model=backend_model,
            base_url=os.getenv("BASE_URL"),
            api_key="any",
            temperature=0 # 排障任务必须为0，保证工具调用稳定性
        )
    # 2. Google Gemini 系列 (使用最新的 OpenAI 兼容接口)
    elif backend_model in ["gemini-3-flash-preview"]:
        # 💡 解决 502 的核心：这里写死 Google 官方端点，绕过你本地失效的 Nginx 代理！
        llm = ChatOpenAI(
            model=backend_model,
            base_url=os.getenv("GEMINI_API_URL"),
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0
            # 如果需要使用 thinking 模型，可以利用 model_kwargs 传入 extra_body
            # model_kwargs={"extra_body": {"google": {"thinking_config": {"thinking_level": "low"}}}}
        )
    else:
        raise ValueError(f"Unsupported backend model: {backend_model}")
        
    return llm

if __name__ == "__main__":
    # 本地测试代码
    try:
        # 测试 Gemini
        print("--- 测试 ---")
        gemini_llm = load_model("gemini-3-flash-preview")
        print(gemini_llm.invoke([HumanMessage(content="你是谁？一句话回答。")]).content)
        
    except Exception as e:
        print(f"调用失败: {e}")