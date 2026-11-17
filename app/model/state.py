"""图的运行时 state：只放 LangGraph 关心的字段（业务对象放 app/model 下）。"""

from operator import add
from typing import Annotated

from pydantic import BaseModel, Field

from app.model.analysis import AnalysisResult


class OverAllState(BaseModel):
    """代码问答图的 state（检索 → 生成）。"""

    question: str
    mid_context: str = ""
    answer: str = ""
    project_id: int
    # region 改动 2026-11-17（多轮）：请求可带历史，检索前先做「指代补全」，生成时把历史作为对话上下文
    # [原代码] 改动前：state 只有 question / mid_context / answer / project_id，
    #           检索永远只用当前这一句（问「那它的超时呢」会因为“它”检索不到任何东西）
    history: list[dict] = []
    retrieval_query: str = ""
    # endregion


class AnalysesState(BaseModel):
    """单文件代码分析图的 state（load → split → Send 并发 → summary）。"""

    file_id: int
    file_path: str = ""
    code: str = ""
    chunks: list[str] = Field(default_factory=list)
    analyses: Annotated[
        list[AnalysisResult],
        add
    ] = Field(default_factory=list)
    result: AnalysisResult | None = None
