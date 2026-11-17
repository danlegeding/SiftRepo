"""建图与编译：节点实现在 app/graph/nodes/ 下，这里只负责接线和 compile。

两张图：
- graph          → 代码问答（检索 → 生成）
- analyses_graph → 单文件代码分析（load_file → split_node → Send 并发 → summary）
"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.graph.nodes.analyze_chunk import analyses_code_chunk_node
from app.graph.nodes.empty_result import empty_result_node
from app.graph.nodes.generate import generate_node
from app.graph.nodes.load_file import load_file
from app.graph.nodes.retrieve import retrieve_node
from app.graph.nodes.split import split_node
from app.graph.nodes.summary import summary_analyses_node
from app.model.state import AnalysesState, OverAllState


def build_code_graph():
    """代码问答图：retrieve_node → generate_node。"""
    builder = StateGraph(OverAllState)
    builder.add_node("retrieve_node", retrieve_node)
    builder.add_node("generate_node", generate_node)
    builder.add_edge(START, "retrieve_node")
    builder.add_edge("retrieve_node", "generate_node")
    builder.add_edge("generate_node", END)
    return builder.compile()


def router(state: AnalysesState) -> str | list[Send]:
    """分流：没有代码块 → 走空结果；有块 → 每块一个 Send，并发分析。"""
    if not state.chunks:
        return "empty_result_node"
    return [
        Send(
            "analyses_code_chunk_node",
            {"content": chunk},
        )
        for chunk in state.chunks
    ]


def build_analysis_graph():
    """代码分析图：load_file → split_node → (Send 并发 | empty_result_node) → summary。"""
    builder = StateGraph(AnalysesState)
    builder.add_node("load_file", load_file)
    builder.add_node("split_node", split_node)
    builder.add_node("analyses_code_chunk_node", analyses_code_chunk_node)
    builder.add_node("summary_analyses_node", summary_analyses_node)
    builder.add_node("empty_result_node", empty_result_node)
    builder.add_edge(START, "load_file")
    builder.add_edge("load_file", "split_node")
    builder.add_conditional_edges(
        "split_node",
        router,
        path_map={
            "analyses_code_chunk_node": "analyses_code_chunk_node",
            "empty_result_node": "empty_result_node",
        },
    )
    builder.add_edge("analyses_code_chunk_node", "summary_analyses_node")
    builder.add_edge("summary_analyses_node", END)
    builder.add_edge("empty_result_node", END)
    return builder.compile()


# 模块级单例：路由层直接 `from app.graph.build import graph, analyses_graph`
graph = build_code_graph()
analyses_graph = build_analysis_graph()
