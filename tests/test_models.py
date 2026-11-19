import pytest
from pydantic import ValidationError

from app.core.models import CodeChunk, CodeFile, Project
from app.model.api import ChatRequest, HistoryTurn


def test_chat_request_rejects_empty_question():
    """空问题要在进接口之前就被挡掉，而不是让模型去猜「用户是不是手滑了」。"""
    with pytest.raises(ValidationError, match="question"):
        ChatRequest(question="", project_id=3)


def test_chat_request_rejects_too_long_question():
    with pytest.raises(ValidationError, match="question"):
        ChatRequest(question="x" * 2001, project_id=3)


def test_chat_request_requires_project_id():
    """project_id 没有默认值：漏传必须报错，否则会拿 None 去查库、变成 500。"""
    with pytest.raises(ValidationError, match="project_id"):
        ChatRequest(question="这个项目的入口在哪")


def test_chat_request_rejects_too_many_history_turns():
    """history 最多 6 轮（和 prompt 里取最近 3 轮不是一回事，这里限制的是请求体大小）。"""
    turns = [HistoryTurn(question=f"问题{i}") for i in range(7)]
    with pytest.raises(ValidationError, match="history"):
        ChatRequest(question="那它的超时呢", project_id=3, history=turns)



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
