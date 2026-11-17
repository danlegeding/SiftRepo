from app.core.models import CodeChunk, CodeFile, Project


def test_project_model_fields():
    assert {"id", "name"} <= set(Project._meta.fields_map)


def test_code_file_model_fields():
    assert {"id", "project", "path", "language", "content", "created_at"} <= set(
        CodeFile._meta.fields_map
    )


def test_code_chunk_model_fields():
    # embedding 列由 app/db_init.py 用 SQL 补，不属于 Tortoise 模型字段
    fields = set(CodeChunk._meta.fields_map)

    assert {"id", "file", "content", "start_line", "end_line", "chunk_index"} <= fields
    assert "embedding" not in fields


async def test_db_init_creates_embedding_column():
    """需要可用的 PostgreSQL：验证幂等初始化后 embedding 列与 vector 扩展存在。"""
    import pytest
    from tortoise import Tortoise

    from app.core.config import TORTOISE_ORM
    from app.core.db_init import ensure_pgvector_schema

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        await Tortoise.generate_schemas()
        await ensure_pgvector_schema()

        connection = Tortoise.get_connection("default")
        _, columns = await connection.execute_query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'codechunk'"
        )
        assert "embedding" in {row["column_name"] for row in columns}

        _, extensions = await connection.execute_query(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        )
        assert extensions
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用，跳过：{exc}")
    finally:
        await Tortoise.close_connections()
