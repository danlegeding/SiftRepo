"""embedding 客户端：只负责「文本 → 向量」，不碰数据库。

模型/维度都走环境变量，客户端懒加载：没配 key 的机器也能 import（只在上传/问答时才报错）。
"""

from dotenv import load_dotenv
from loguru import logger
from langchain.embeddings import init_embeddings
import asyncio
import os

# 不做 override：外部（容器 / CI / 命令行）注入的环境变量优先于文件
load_dotenv()

# 换 embedding 模型时，维度必须同步改（列定义与写入都会用它）
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
DEFAULT_EMBEDDING_MODEL = "openai:text-embedding-3-small"

_model = None


def get_embedding_model():
    """返回 embedding 客户端（首次调用时创建，之后复用）。

    延迟到调用期构造，避免 import 阶段就要求 API Key（CI / 单测 / 未配 key 的机器
    否则连模块都导不进来）。
    """
    global _model
    if _model is not None:
        return _model

    api_key = os.getenv("CLOSEAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未找到 CLOSEAI_API_KEY，请在项目根目录的 .env 中配置后再上传或问答"
        )

    model_name = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    logger.info("embedding 客户端就绪：model={} dim={}", model_name, EMBEDDING_DIM)
    _model = init_embeddings(
        model=model_name,
        api_key=api_key,
        base_url=os.getenv("CLOSEAI_BASE_URL"),
    )
    return _model


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """在线程中批量生成文本向量，避免阻塞 FastAPI 事件循环。"""
    if not texts:
        return []

    return await asyncio.to_thread(
        get_embedding_model().embed_documents,
        texts,
    )
