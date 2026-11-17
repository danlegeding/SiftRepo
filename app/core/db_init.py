"""补齐 Tortoise 建表时无法声明的部分：pgvector 扩展 + `codechunk.embedding` 列。

背景：Tortoise 没有 `vector` 字段类型，`app/models.py` 里的 `CodeChunk` 只能建出普通列，
向量列必须用 SQL 补。这里做幂等初始化：

- `CREATE EXTENSION IF NOT EXISTS vector`
- `ALTER TABLE IF EXISTS codechunk ADD COLUMN IF NOT EXISTS embedding vector(<dim>)`

调用方：`app/services/embedding.py` 在首次读写向量前调用，因此不依赖启动顺序；
两条语句都幂等，多进程重复执行也安全。
"""

from loguru import logger
from tortoise import connections

DEFAULT_EMBEDDING_DIM = 1536

_ready_dims: set[int] = set()


async def ensure_pgvector_schema(dim: int = DEFAULT_EMBEDDING_DIM) -> None:
    """幂等地创建 pgvector 扩展与 `codechunk.embedding` 列。"""
    if dim in _ready_dims:
        return

    connection = connections.get("default")
    await connection.execute_query("CREATE EXTENSION IF NOT EXISTS vector")
    await connection.execute_query(
        f"ALTER TABLE IF EXISTS codechunk "
        f"ADD COLUMN IF NOT EXISTS embedding vector({dim})"
    )
    _ready_dims.add(dim)
    logger.info("pgvector 就绪：codechunk.embedding vector({})", dim)
# endregion
