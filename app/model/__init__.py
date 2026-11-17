"""model 包：跨层的 Pydantic 契约（接口请求体、图 state、分析结果）。

和 app/core/models.py 的分工：
- app/core/models.py  → **ORM 表定义**（Tortoise，对应数据库里的表）
- app/model/          → **数据契约**（Pydantic，用于接口入参/出参与图内部）
"""

from app.model.analysis import AnalysisIssue, AnalysisResult
from app.model.api import (
    AnalysisRequest,
    ChatRequest,
    HistoryTurn,
)
from app.model.state import AnalysesState, OverAllState

__all__ = [
    "AnalysisIssue",
    "AnalysisResult",
    "AnalysisRequest",
    "ChatRequest",
    "HistoryTurn",
    "AnalysesState",
    "OverAllState",
]
