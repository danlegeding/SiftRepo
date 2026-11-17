"""节点：只依据检索到的代码作答，并要求引用文件与行号。"""

from app.graph.nodes.query_builder import format_history
from app.model.state import OverAllState
from app.services.deepseek_llm import get_llm_model


def _to_text(content) -> str:
    """模型 content 可能是 str 或 list[dict]（带思考/多模态），统一成 str。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


async def generate_node(state: OverAllState) -> dict:
    """只依据检索到的代码作答，并要求引用文件与行号。"""
    history_text = format_history(state.history)   # 带历史
    history_block = (
        f"\n之前的对话（只用于理解“它/那个”指什么，不能当代码依据）：\n{history_text}\n"
        if history_text
        else ""
    )
    prompt = f"""你是一个严谨的代码分析助手，负责回答用户关于指定项目的问题。

请严格遵守以下规则：
1. 先直接回答问题，不要写冗长的背景介绍。
2. 只根据提供的代码上下文回答，不要把猜测当作事实。
3. 如果问题询问执行流程，按照实际执行顺序解释。
4. 如果问题询问某个功能，说明相关文件、关键逻辑及其作用。
5. 如果上下文不足以回答，明确指出缺少什么信息。
6. 使用清晰的中文，优先分点说明，避免重复和空泛评价。
7. 只有在上下文能够支持时，才引用文件路径和行号。
8. 对于上下文中未展示的分支、函数实现或调用关系，不得依据常见编程模式补全其行为。
9. 可以提出待验证的可能性，但必须标记为假设，不得写入已确认的流程。
10. 如果问题里的“它/那个”指前面聊过的东西，先明确你理解成什么，再作答。
{history_block}
建议结构：
- 结论：一两句话回答。
- 具体依据：结合检索到的代码解释。
- 补充说明：仅在必要时指出限制。

用户问题：
{state.question}

检索到的代码上下文：
{state.mid_context}
"""
    response = await get_llm_model().ainvoke(prompt)
    return {"answer": _to_text(response.content)}   # _to_text 兜底 list 型 content
