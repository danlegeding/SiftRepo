"""节点：检索该项目的相关代码块，拼成上下文（进 state.mid_context）。"""

from app.graph.nodes.query_builder import build_retrieval_query
from app.model.state import OverAllState
from app.services.vector_store import retrieve


async def retrieve_node(state: OverAllState) -> dict:
    """检索该项目的相关代码块，拼成上下文。"""
    query = build_retrieval_query(state.question, state.history)   # 指代补全
    context = await retrieve(query, state.project_id)
    return {"mid_context": f"上下文：\n{context}", "retrieval_query": query}
