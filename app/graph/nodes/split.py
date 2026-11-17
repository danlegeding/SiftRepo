"""节点：把文件内容切成待分析的块（空文件返回空列表，走 empty_result 分支）。"""

from app.model.state import AnalysesState
from app.services.code_chunk_analysis import split_code_for_analyses


async def split_node(state: AnalysesState) -> dict:
    MAX_analyses_CHUNKS = 3000
    if not state.code.strip():
        return {"chunks": []}
    if len(state.code) <= MAX_analyses_CHUNKS:
        return {
            "chunks": [state.code]
        }
    return {
        "chunks": split_code_for_analyses(state.code)
    }
