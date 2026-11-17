"""HTTP 层入口：把各业务路由聚成一个 api_router，交给 app.main 挂载。"""

from fastapi import APIRouter

from app.api.routers import analysis, chat, projects

api_router = APIRouter()
api_router.include_router(projects.router)
api_router.include_router(chat.router)
api_router.include_router(analysis.router)
