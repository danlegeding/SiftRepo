"""节点：把各块的分析结果汇总成一份文件级报告。"""

from app.model.state import AnalysesState
from app.services.code_chunk_analysis import summarize_analyses


async def summary_analyses_node(state: AnalysesState) -> dict:
    result = await summarize_analyses(
        analyses=state.analyses,
        file_path=state.file_path,
    )
    return {"result": result}
