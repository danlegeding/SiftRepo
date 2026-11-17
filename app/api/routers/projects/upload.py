"""项目上传接口：收 ZIP → 过滤 → 切块 → 批量向量化 → 落库。

任一步失败都会删掉本次创建的项目（级联删文件与代码块），不留「有记录没向量」的脏数据。
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


@router.post("/upload")
async def upload_project(file: UploadFile = File(...)):
    """上传 ZIP：过滤文件 → 切块落库 → 批量生成向量。"""
    data = await file.read()
    if len(data) > MAX_ZIP_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"ZIP 超过上限（{MAX_ZIP_BYTES // 1024 // 1024} MB），请裁剪后再上传",
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=400, detail="上传的文件不是有效的 ZIP 压缩包"
        ) from exc

    project = await Project.create(name=file.filename)
    all_codechunks: list[CodeChunk] = []
    files: list[dict] = []

    try:
        with archive as z:
            for name in z.namelist():
                if name.endswith("/"):
                    continue

                path = PurePosixPath(name)
                if any(part in EXCLUDED_DIRS for part in path.parts):
                    continue
                # 后缀比较大写不敏感（.PY / .Py 也算）
                if path.suffix.lower() not in SUPPORTED_EXTENTION:
                    continue

                try:
                    content = z.read(name).decode("utf-8")
                except UnicodeDecodeError:
                    continue

                if len(files) >= MAX_FILES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件数超过上限（{MAX_FILES}），请只上传需要的子目录",
                    )

                code_file = await CodeFile.create(
                    project=project,
                    path=name,
                    language=path.suffix.lower(),
                    content=content,
                )

                chunks = chunk_code(content, chunk_size=500, overlap=50)
                if len(all_codechunks) + len(chunks) > MAX_CHUNKS:
                    raise HTTPException(
                        status_code=413,
                        detail=f"代码块数超过上限（{MAX_CHUNKS}），请缩小上传范围",
                    )

                await CodeChunk.bulk_create(
                    [
                        CodeChunk(
                            file=code_file,
                            content=chunk["content"],
                            start_line=chunk["start_line"],
                            end_line=chunk["end_line"],
                            chunk_index=chunk["chunk_index"],
                        )
                        for chunk in chunks
                    ]
                )
                # bulk_create 不回填主键，重新查一次拿到 id（新文件，按 chunk_index 排序稳定）
                all_codechunks.extend(
                    await CodeChunk.filter(file=code_file).order_by("chunk_index")
                )

                files.append({"path": name, "chunks_count": len(chunks)})

        # 所有代码块落库后再分批生成向量，失败会回滚整个项目
        for i in range(0, len(all_codechunks), EMBED_BATCH_SIZE):
            batch = all_codechunks[i:i + EMBED_BATCH_SIZE]
            vectors = await embed_texts([chunk.content for chunk in batch])
            await save_embeddings(batch, vectors)
    except Exception:
        await project.delete()
        raise

    return {
        "project_id": project.id,
        "filename": file.filename,
        "files_count": len(files),
        "chunks_count": len(all_codechunks),
        "files": files,
    }
