"""HTTP 请求体契约：接口层只认这些，内部函数不直接收原始 dict。"""

from pydantic import BaseModel, Field


# region 改动 2026-11-17（多轮）：请求可带最近几轮问答，用于「指代补全」和生成时的对话上下文
# 现在的约定：history 由前端传，最多 6 轮；后端只读、不落库（不引入 thread_id / checkpointer）。
# [原代码] 改动前只有 question + project_id，图里 mid_context 恒为空字符串，
#           每轮都是独立问答（追问“那它的超时呢”检索不到东西）。
# [原代码] 改动前 history 是子类 ChatRequestWithHistory(ChatRequest)；端点只认这一个请求体、
#           父类没有独立使用点，已合并进 ChatRequest（缺省 history=[]，老请求体不用改）。
class HistoryTurn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    answer: str = Field(default="", max_length=8000)


# region 改动 2026-11-17：问题长度校验 + 项目不存在返回 404
# [原代码] 改动前：question 无长度约束，也不校验项目是否存在（传错 id 返回 200 空回答）：
#     class ChatRequest(BaseModel):
#         question: str
#         project_id: int
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    project_id: int
    history: list[HistoryTurn] = Field(default_factory=list, max_length=6)
# endregion


class AnalysisRequest(BaseModel):
    file_id: int
