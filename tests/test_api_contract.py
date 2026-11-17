"""接口契约测试：路由表、参数校验、错误码，以及用 stub 替换「检索 + LLM」的 happy path。

需要可用的 PostgreSQL（TestClient 会触发 lifespan 里的 Tortoise 初始化）；
数据库不可用时整体 skip，而不是报错——本地没起 docker 也能跑其余测试。
"""

import app.graph.nodes.generate as generate_module
import app.graph.nodes.retrieve as retrieve_module
import pytest
from fastapi.testclient import TestClient

from app.main import app

EXPECTED_PATHS = {
    "/analysis/",
    "/chat/",
    "/projects",
    "/projects/upload",
    "/projects/{project_id}/files",
}

STUB_CONTEXT = "文件：src/demo.py\n行号：1-2\n代码内容：\ndef add(a, b):\n    return a + b"


class _StubResponse:
    content = "结论：加法实现在 src/demo.py 的 add 函数里。"


class _StubLLM:
    async def ainvoke(self, prompt: str):  # noqa: ARG002 - 只验证调用链
        return _StubResponse()


@pytest.fixture(scope="module")
def client():
    try:
        with TestClient(app) as test_client:
            yield test_client
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用，跳过接口测试：{exc}")


@pytest.fixture
def stub_retrieval(monkeypatch):
    async def fake_retrieve(query: str, project_id: int, limit: int = 5):  # noqa: ARG001
        return STUB_CONTEXT

    monkeypatch.setattr(retrieve_module, "retrieve", fake_retrieve)
    monkeypatch.setattr(generate_module, "get_llm_model", lambda: _StubLLM())


def test_openapi_paths_are_stable(client):
    paths = {path for path in app.openapi()["paths"]}

    assert paths == EXPECTED_PATHS


def test_list_projects_contract(client):
    response = client.get("/projects")

    assert response.status_code == 200
    body = response.json()
    assert {"total", "items"} <= set(body)
    assert isinstance(body["items"], list)


def test_list_project_files_returns_404_for_missing_project(client):
    response = client.get("/projects/999999/files")

    assert response.status_code == 404
    assert "项目不存在" in response.json()["message"]


def test_list_project_files_contract(client):
    projects = client.get("/projects").json()["items"]
    if not projects:
        pytest.skip("库里没有项目，跳过该用例")

    response = client.get(f"/projects/{projects[0]['project_id']}/files")

    assert response.status_code == 200
    body = response.json()
    assert {"files", "chunks", "chunks_total", "chunks_truncated"} <= set(body)


def test_chat_rejects_empty_question(client):
    response = client.post("/chat/", json={"question": "", "project_id": 1})

    assert response.status_code == 422


def test_chat_rejects_too_long_history(client):
    history = [{"question": f"q{i}", "answer": "a"} for i in range(7)]
    response = client.post(
        "/chat/", json={"question": "代码在哪", "project_id": 1, "history": history}
    )

    assert response.status_code == 422


def test_chat_returns_404_for_missing_project(client):
    response = client.post("/chat/", json={"question": "代码在哪", "project_id": 999999})

    assert response.status_code == 404
    assert "项目不存在" in response.json()["message"]


def test_chat_happy_path_with_stubbed_retrieval_and_llm(client, stub_retrieval):
    projects = client.get("/projects").json()["items"]
    if not projects:
        pytest.skip("库里没有项目，跳过该用例")

    response = client.post(
        "/chat/",
        json={"question": "加法在哪实现", "project_id": projects[0]["project_id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == _StubResponse.content
    assert body["retrieval_query"] == "加法在哪实现"


def test_chat_completes_deictic_question_when_history_given(client, stub_retrieval):
    projects = client.get("/projects").json()["items"]
    if not projects:
        pytest.skip("库里没有项目，跳过该用例")

    response = client.post(
        "/chat/",
        json={
            "question": "那它的参数呢",
            "project_id": projects[0]["project_id"],
            "history": [{"question": "加法在哪实现", "answer": "在 src/demo.py"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["retrieval_query"] == "加法在哪实现 那它的参数呢"


def test_analysis_returns_404_for_missing_file(client):
    response = client.post("/analysis/", json={"file_id": 999999})

    assert response.status_code == 404
    assert "文件不存在" in response.json()["message"]
