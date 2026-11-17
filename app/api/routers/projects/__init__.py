"""projects 路由聚合：一个端点一个文件，这里只负责拼起来。"""

from fastapi import APIRouter

from app.api.routers.projects import query, upload

router = APIRouter()
router.include_router(query.router)
router.include_router(upload.router)
