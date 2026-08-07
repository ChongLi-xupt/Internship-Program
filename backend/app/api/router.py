"""API router — registers all sub-routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.knowledge import router as knowledge_router
from app.api.ingestion import router as ingestion_router
from app.api.chat import router as chat_router
from app.api.datasource import router as datasource_router
from app.api.semantic import router as semantic_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(users_router, prefix="/users", tags=["用户管理"])
api_router.include_router(knowledge_router, prefix="/knowledge-bases", tags=["知识库"])
api_router.include_router(ingestion_router, prefix="", tags=["文档处理"])
api_router.include_router(chat_router, prefix="/chat", tags=["对话问答"])
api_router.include_router(datasource_router, prefix="/datasources", tags=["数据源"])
api_router.include_router(semantic_router, prefix="/semantic", tags=["语义层"])
api_router.include_router(admin_router, prefix="/admin", tags=["系统管理"])
