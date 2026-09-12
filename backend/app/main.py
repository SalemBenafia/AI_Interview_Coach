"""
app/main.py - FastAPI application factory. All module routers registered here.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging import configure_logging
from app.core.settings import settings

configure_logging(settings.LOG_LEVEL)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Interview Coach API starting", env=settings.APP_ENV)
    try:
        from app.core.redis import get_redis
        await get_redis().ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis unavailable", error=str(exc))
    yield
    logger.info("AI Interview Coach API shutting down")
    from app.core.redis import close_redis
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Interview Coach API",
        description="Real-time AI interview coaching platform — live voice interview "
                    "simulator for job training, built on WebRTC + LangGraph + OpenRouter.",
        version="1.0.0",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{ms}ms"
        logger.debug("request", method=request.method, path=request.url.path,
                     status=response.status_code, duration_ms=ms)
        return response

    @app.exception_handler(404)
    async def not_found(_req, _exc):
        return JSONResponse(
            content={"success": False, "error": {"code": "NOT_FOUND", "message": "Resource not found."}},
            status_code=404,
        )

    @app.exception_handler(500)
    async def internal_error(_req, exc):
        logger.error("unhandled", error=str(exc))
        return JSONResponse(
            content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "Internal error."}},
            status_code=500,
        )

    p = settings.API_V1_PREFIX

    from app.modules.auth.router import router as auth_router
    from app.modules.auth.me_router import router as me_router
    from app.modules.users.router import router as users_router
    from app.modules.catalog.router import router as catalog_router
    from app.modules.target_roles.router import router as target_roles_router
    from app.modules.interviews.router import router as interviews_router
    from app.modules.livekit.router import router as livekit_router
    from app.modules.notifications.router import router as notifications_router
    from app.modules.admin.users.router import router as admin_users_router
    from app.modules.admin.agents.router import router as admin_agents_router
    from app.modules.admin.flows.router import router as admin_flows_router
    from app.modules.admin.content.router import router as admin_content_router
    from app.modules.admin.analytics.router import router as admin_analytics_router
    from app.modules.admin.monitoring.router import router as admin_monitoring_router
    from app.modules.admin.security.router import router as admin_security_router
    from app.modules.ws.router import router as ws_router

    for router in [
        auth_router, me_router, users_router, catalog_router, target_roles_router,
        interviews_router, livekit_router, notifications_router,
        admin_users_router, admin_agents_router, admin_flows_router,
        admin_content_router, admin_analytics_router,
        admin_monitoring_router, admin_security_router,
    ]:
        app.include_router(router, prefix=p)

    app.include_router(ws_router)  # no prefix — uses /ws path directly

    if settings.is_development:
        # Text-turn endpoint for automated tests only -- bypasses the voice
        # transport, not the agent logic. Never mounted outside dev/CI.
        from app.modules.interviews.dev_router import router as dev_interviews_router
        app.include_router(dev_interviews_router, prefix=p)

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": "ai-interview-coach-api", "version": "1.0.0"}

    return app


app = create_app()
