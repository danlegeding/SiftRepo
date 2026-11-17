"""代码分析接口：POST /analysis/ ——按 file_id 跑「单文件分析图」。"""

from fastapi import APIRouter

from app.graph.build import analyses_graph
from app.model.api import AnalysisRequest

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"]
)


@router.post("/")
async def analyze(request: AnalysisRequest):
    final_result = await analyses_graph.ainvoke(
        {"file_id": request.file_id}
    )
    return final_result["result"]
