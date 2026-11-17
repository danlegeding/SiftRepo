"""节点：按 file_id 从数据库取出文件路径与内容。"""

from fastapi import HTTPException

from app.core.models import CodeFile
from app.model.state import AnalysesState


async def load_file(state: AnalysesState) -> dict:
    code_file = await CodeFile.get_or_none(id=state.file_id)
    if code_file is None:
        raise HTTPException(
            status_code=404,
            detail="文件不存在"
        )
    return {
        "file_path": code_file.path,
        "code": code_file.content or ""
    }
