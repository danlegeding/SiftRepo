"""对话接口：POST /chat/ ——校验项目存在后走「检索 → 生成」图。"""

from fastapi import APIRouter, HTTPException

from app.core.models import Project
from app.graph.build import graph
from app.model.api import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


# region 改动 2026-11-17（整理）：请求体模型搬到 app/model/api.py（接口契约与路由分开）
# [原代码] 改动前：ChatRequest / HistoryTurn / ChatRequestWithHistory 三个类直接写在本文件里。
# 对应的行为改动（问题长度校验、项目不存在 404、支持多轮 history）见 app/model/api.py 与下方端点。
@router.post("/")
async def chat(request: ChatRequest):
    """针对某个项目提问：先校验项目存在，再走「检索 → 生成」图。"""
    project = await Project.get_or_none(id=request.project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"项目不存在：project_id={request.project_id}",
        )

    response = await graph.ainvoke(
        {
            "question": request.question,
            "mid_context": "",
            "answer": "",
            "project_id": request.project_id,
            # 历史是 Pydantic 对象，state/checkpoint 只吃 JSON 原生类型，这里降到 dict
            "history": [turn.model_dump(mode="json") for turn in request.history],
        }
    )

    return {
        "answer": response["answer"],
        "retrieval_query": response.get("retrieval_query", ""),   # 回显检索用的查询（便于排查）
    }
# endregion
