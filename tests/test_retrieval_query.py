"""多轮指代补全的单元测试：不依赖数据库、不调模型。"""

from app.graph.nodes.query_builder import (
    HISTORY_ANSWER_MAX_CHARS,
    HISTORY_TURNS_FOR_PROMPT,
    build_retrieval_query,
    format_history,
)


def test_self_contained_question_is_unchanged():
    # 自包含问题 + 有历史 → 不能被上一轮话题污染
    history = [{"question": "登录逻辑在哪个文件？", "answer": "在 app/api/routers/auth.py"}]

    assert build_retrieval_query("这个项目的整体架构是什么", history) == "这个项目的整体架构是什么"


def test_deictic_question_is_prefixed_with_previous_question():
    history = [{"question": "登录逻辑在哪个文件？", "answer": "在 auth.py"}]

    query = build_retrieval_query("那它的超时呢", history)

    assert query == "登录逻辑在哪个文件？ 那它的超时呢"


def test_short_question_is_treated_as_followup():
    history = [{"question": "chunker 怎么切代码？", "answer": "按 500 字切"}]

    assert build_retrieval_query("为什么", history).startswith("chunker 怎么切代码？")


def test_no_history_returns_question_as_is():
    assert build_retrieval_query("那它呢", []) == "那它呢"
    assert build_retrieval_query("那它呢", None) == "那它呢"


def test_empty_previous_question_is_ignored():
    history = [{"question": "", "answer": ""}]

    assert build_retrieval_query("那它的超时呢", history) == "那它的超时呢"


def test_format_history_keeps_only_recent_turns():
    history = [
        {"question": f"问题{i}", "answer": f"答案{i}"} for i in range(HISTORY_TURNS_FOR_PROMPT + 2)
    ]

    text = format_history(history)

    assert f"问题{len(history) - 1}" in text
    assert "问题0" not in text


def test_format_history_truncates_long_answer():
    history = [{"question": "问", "answer": "答" * (HISTORY_ANSWER_MAX_CHARS + 50)}]

    text = format_history(history)

    assert "答" * HISTORY_ANSWER_MAX_CHARS in text
    assert "答" * (HISTORY_ANSWER_MAX_CHARS + 1) not in text


def test_format_history_empty():
    assert format_history([]) == ""
