"""节点：分析单个代码块（由 router 用 Send 并发扇出，入参是 dict 而不是 state）。"""

from app.services.code_chunk_analysis import analyses_code_chunk


async def analyses_code_chunk_node(state: dict) -> dict:
    """传入的是字典而非 str 类型的 content，是因为 router 传入的是字典。"""
    one_chunk_result = await analyses_code_chunk(state["content"])
    return {
        "analyses": [one_chunk_result]
    }
