"""对话接口：POST /chat/ ——校验项目存在后走「检索 → 生成」图。"""

from fastapi import APIRouter, HTTPException

from app.core.models import Project
from app.graph.build import graph
from app.model.api import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


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
