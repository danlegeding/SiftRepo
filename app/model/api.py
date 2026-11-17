"""HTTP 请求体契约：接口层只认这些，内部函数不直接收原始 dict。"""

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(default="", max_length=8000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    project_id: int
    history: list[HistoryTurn] = Field(default_factory=list, max_length=6)


class AnalysisRequest(BaseModel):
    file_id: int
