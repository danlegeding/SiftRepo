"""检索语句构造：把「那它的超时呢」补全成能检索的查询，并把历史压成 prompt 片段。

纯确定性逻辑，不调用模型，方便单测。
"""

import re

HISTORY_TURNS_FOR_PROMPT = 3      # 拼进 prompt 的历史最多几轮
HISTORY_ANSWER_MAX_CHARS = 200    # 每条历史答案截断长度，防止 prompt 失控
DEICTIC_PATTERN = re.compile(
    r"(它|他|她|这个|那个|这些|那些|上面|刚才|之前|上述|该文件|该函数|该接口|其实现|这里)"
)
# 这些说法本身已经带上下文，不该被当成「指代上一个问题」
SELF_CONTAINED_PATTERN = re.compile(
    r"(这个项目|该项目|本项目|这个仓库|这个代码库|这个代码仓库|整个项目)"
)
SHORT_QUESTION_CHARS = 8          # 太短的问题（如「为什么？」）也带上上一轮


def _last_question(history: list[dict]) -> str:
    """取最近一轮的用户问题。"""
    for turn in reversed(history or []):
        if isinstance(turn, dict) and turn.get("question"):
            return str(turn["question"]).strip()
    return ""


def build_retrieval_query(question: str, history: list[dict]) -> str:
    """把「那它的超时呢」这类依赖上下文的问题，补全成可检索的查询。

    规则（不调用模型、纯确定性）：
    - 没有问题历史 → 原样返回；
    - 当前问题含指代词（它/这个/刚才…）或过短 → 「上一轮问题 + 当前问题」；
    - 其他情况 → 原样返回（避免历史污染检索）。
    """
    previous = _last_question(history)
    if not previous:
        return question

    # 「这个项目/本项目」这类说法自身已带上下文，不补全
    if SELF_CONTAINED_PATTERN.search(question):
        return question

    # 含指代词（它/刚才/该函数…）或问题过短 → 拼上上一轮问题
    if DEICTIC_PATTERN.search(question) or len(question.strip()) <= SHORT_QUESTION_CHARS:
        return f"{previous} {question}"

    return question


def format_history(history: list[dict]) -> str:
    """把最近几轮问答压成 prompt 里的一段文字。"""
    turns = [turn for turn in (history or []) if isinstance(turn, dict) and turn.get("question")]
    if not turns:
        return ""

    lines = []
    for turn in turns[-HISTORY_TURNS_FOR_PROMPT:]:
        answer = str(turn.get("answer") or "").strip()
        if len(answer) > HISTORY_ANSWER_MAX_CHARS:
            answer = answer[:HISTORY_ANSWER_MAX_CHARS] + "……"
        lines.append(f"- 问：{str(turn['question']).strip()}")
        if answer:
            lines.append(f"  答：{answer}")
    return "\n".join(lines)
