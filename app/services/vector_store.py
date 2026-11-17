"""向量存储：把向量写进 codechunk 表、按余弦距离检索回代码片段。

embedding.py 只算向量，这里负责和 PostgreSQL / pgvector 打交道。
"""

from loguru import logger
import asyncio
import time

from tortoise import connections

from app.core.db_init import ensure_pgvector_schema
from app.services.embedding import EMBEDDING_DIM, embed_texts, get_embedding_model


async def save_embeddings(chunks, vectors) -> None:
    """把生成的向量写回 CodeChunk（单条 UPDATE，Tortoise 无批量 update API）。"""
    if len(chunks) != len(vectors):
        raise ValueError("代码块数量与向量数量不一致")

    await ensure_pgvector_schema(EMBEDDING_DIM)   # 改动：写入前先确保向量列存在

    connection = connections.get("default")
    for chunk, vector in zip(chunks, vectors):
        await connection.execute_query(
            "UPDATE codechunk SET embedding = $1::vector WHERE id = $2",
            [str(vector), chunk.id],
        )


async def embed_code_chunk(chunk) -> None:
    """兼容单块调用：生成并写入一个代码块的向量。"""
    vectors = await embed_texts([chunk.content])
    await save_embeddings([chunk], vectors)


async def retrieve(query: str, project_id: int, limit: int = 5) -> str:
    """按余弦距离检索相关代码块，返回拼好的上下文文本。"""
    await ensure_pgvector_schema(EMBEDDING_DIM)

    connection = connections.get("default")

    embedding_start = time.perf_counter()
    query_vector = await asyncio.to_thread(
        get_embedding_model().embed_query,
        query,
    )
    embedding_elapsed_ms = (time.perf_counter() - embedding_start) * 1000

    retrieval_start = time.perf_counter()
    _, rows = await connection.execute_query(
        """
        SELECT
            codechunk.id AS chunk_id,
            codefile.path AS file_path,
            codechunk.content AS chunk_content,
            codechunk.start_line AS chunk_start_line,
            codechunk.end_line AS chunk_end_line
        FROM codechunk
        JOIN codefile ON codechunk.file_id = codefile.id
        WHERE codechunk.embedding IS NOT NULL
          AND codefile.project_id = $1
        ORDER BY codechunk.embedding <=> $2::vector
        LIMIT $3
        """,
        [project_id, str(query_vector), limit],
    )
    retrieval_elapsed_ms = (time.perf_counter() - retrieval_start) * 1000

    logger.info(
        "检索完成 | project_id={} | 命中={} | embedding_ms={:.1f} | db_ms={:.1f}",
        project_id,
        len(rows),
        embedding_elapsed_ms,
        retrieval_elapsed_ms,
    )

    if not rows:
        return "没有检索到相关代码。"

    contexts = []
    for row in rows:
        contexts.append(
            f"文件：{row['file_path']}\n"
            f"行号：{row['chunk_start_line']}-{row['chunk_end_line']}\n"
            f"相关代码：\n{row['chunk_content']}"
        )

    return "\n\n--- 相关代码片段 ---\n\n".join(contexts)
