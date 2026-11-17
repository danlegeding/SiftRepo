"""代码分析的数据契约（给模型的结构化输出、也是接口的返回结构）。"""

from pydantic import BaseModel


class AnalysisIssue(BaseModel):
    level: str
    description: str
    suggestion: str


class AnalysisResult(BaseModel):
    summary: str
    issues: list[AnalysisIssue]
    strengths: list[str]
    optimization: list[str]
