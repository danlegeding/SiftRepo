"""节点：文件为空时的兜底结果。"""

from app.model.analysis import AnalysisResult
from app.model.state import AnalysesState


async def empty_result_node(state: AnalysesState) -> dict:
    return {
        "result": AnalysisResult(
            summary="文件为空，无法进行代码分析。",
            issues=[],
            strengths=[],
            optimization=["请上传包含代码的文件后重试。"],
        )
    }
