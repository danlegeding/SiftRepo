from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from loguru import logger
import os

load_dotenv()

# 延迟初始化：避免 import 阶段就要求 API Key（否则单元测试/导入模块都会被卡住）
_model: ChatDeepSeek | None = None


def get_llm_model() -> ChatDeepSeek:
    """返回大模型客户端（首次调用时创建，之后复用）。

    Raises:
        RuntimeError: 未配置 DEEPSEEK_API_KEY 时抛出，提示去 .env 里补。
    """
    global _model
    if _model is not None:
        return _model

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未找到 DEEPSEEK_API_KEY，请在项目根目录的 .env 中配置")

    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    extra_body = None
    if os.getenv("DEEPSEEK_DISABLE_THINKING", "").lower() in {"1", "true", "yes"}:
        extra_body = {"thinking": {"type": "disabled"}}

    _model = ChatDeepSeek(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        extra_body=extra_body,
    )
    # endregion
    logger.info("大模型客户端就绪：model={} base_url={}", model_name, base_url)
    return _model
