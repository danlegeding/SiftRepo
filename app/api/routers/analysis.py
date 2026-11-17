"""代码分析接口：POST /analysis/ ——按 file_id 跑「单文件分析图」。"""

from fastapi import APIRouter

from app.graph.build import analyses_graph
from app.model.api import AnalysisRequest

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"]
)


# region 改动 2026-11-17（整理）：请求体模型搬到 app/model/api.py
# [原代码] 改动前：class AnalysisRequest(BaseModel): file_id: int 直接写在本文件里。
@router.post("/")
async def analyze(request: AnalysisRequest):
    final_result = await analyses_graph.ainvoke(
        {"file_id": request.file_id}
    )
    return final_result["result"]
# endregion
