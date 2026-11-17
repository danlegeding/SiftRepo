"""项目列表与文件清单接口（只读）。

GET /projects                   项目列表（带文件数、代码块数）
GET /projects/{project_id}/files 某项目的文件清单与代码块行号
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import PurePosixPath
import io
import zipfile
from app.core.models import Project, CodeFile, CodeChunk
from app.services.chunker import chunk_code
from app.services.embedding import embed_texts
from app.services.vector_store import save_embeddings
from app.services.file_filter import SUPPORTED_EXTENTION
from app.api.routers.projects.limits import (
    EMBED_BATCH_SIZE,
    EXCLUDED_DIRS,
    MAX_CHUNK_ROWS,
    MAX_CHUNKS,
    MAX_FILES,
    MAX_ZIP_BYTES,
)


router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("")
async def list_projects(limit: int = 50) -> dict:
    """列出项目（id、名称、文件数、代码块数），前端用它替代直连数据库。"""
    limit = max(1, min(limit, 200))
    projects = await Project.all().order_by("-id").limit(limit)

    items = []
    for project in projects:
        items.append(
            {
                "project_id": project.id,
                "name": project.name,
                "files_count": await CodeFile.filter(project_id=project.id).count(),
                "chunks_count": await CodeChunk.filter(
                    file__project_id=project.id
                ).count(),
            }
        )
    return {"total": len(items), "items": items}


@router.get("/{project_id}/files")
async def list_project_files(project_id: int) -> dict:
    """列出某个项目下的文件与代码块起止行（前端「代码分析」页用）。"""
    project = await Project.get_or_none(id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    files = await CodeFile.filter(project_id=project_id).order_by("id")
    chunk_total = await CodeChunk.filter(file__project_id=project_id).count()
    chunks = (
        await CodeChunk.filter(file__project_id=project_id)
        .order_by("file_id", "chunk_index")
        .limit(MAX_CHUNK_ROWS)
    )

    # 每个文件的行号范围由它所有代码块推出来
    line_range: dict[int, list[int | None]] = {}
    chunk_rows = []
    for chunk in chunks:
        span = line_range.setdefault(chunk.file_id, [None, None])
        if chunk.start_line is not None:
            span[0] = chunk.start_line if span[0] is None else min(span[0], chunk.start_line)
        if chunk.end_line is not None:
            span[1] = chunk.end_line if span[1] is None else max(span[1], chunk.end_line)
        chunk_rows.append(
            {
                "file_id": chunk.file_id,
                "chunk_index": chunk.chunk_index,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
        )

    path_by_file: dict[int, str] = {}
    file_items = []
    for code_file in files:
        path_by_file[code_file.id] = code_file.path
        start_line, end_line = line_range.get(code_file.id, [None, None])
        file_items.append(
            {
                "file_id": code_file.id,
                "path": code_file.path,
                "language": code_file.language or "",
                "start_line": start_line,
                "end_line": end_line,
            }
        )

    # 代码块行里补上 path，前端表格直接用（前端没有再按 file_id 关联）
    for row in chunk_rows:
        row["path"] = path_by_file.get(row["file_id"], "")

    return {
        "project_id": project.id,
        "project_name": project.name,
        "files": file_items,
        "chunks": chunk_rows,
        "chunks_total": chunk_total,
        "chunks_truncated": chunk_total > len(chunk_rows),
    }
# endregion
