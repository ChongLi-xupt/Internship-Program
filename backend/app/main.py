"""
FastAPI application entry point.
Mounts all routers, middleware, and lifecycle handlers.
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup & shutdown."""
    # Startup
    from app.core.tenant import init_tenant_filter
    from app.vector.base import get_vector_store
    from app.llm.base import validate_llm_config

    init_tenant_filter()

    # Fail loudly on incoherent model config (e.g. DeepSeek without a
    # separate embedding endpoint) instead of dying on the first upload.
    for problem in validate_llm_config():
        print(f"⚠️  LLM CONFIG: {problem}")

    # Ensure vector store is reachable (lazy connect on first use)
    _ = get_vector_store()

    print(
        f"🚀 {settings.app_name} started | env={settings.app_env} | "
        f"LLM={settings.llm_provider} | "
        f"embedding={settings.embedding_provider}:{settings.embedding_model}"
        f"({settings.embedding_dimensions}d)"
    )
    yield
    # Shutdown
    print(f"👋 {settings.app_name} shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Enterprise RAG Q&A & Smart Data Query System",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(api_router, prefix="/api/v1")

    # Health check
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "0.1.0",
            "llm_provider": settings.llm_provider,
            "vector_store": settings.vector_store,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
