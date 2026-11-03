import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import (
    analyses,
    health,
    metrics,
    predictions,
    pull_requests,
    repositories,
    tests,
    webhooks,
)
from app.core.config import settings
from app.core.database import check_database_health
from app.core.logging import correlation_id_ctx, get_logger, setup_logging

# Initialize Structured Logging
setup_logging(debug=settings.DEBUG)
logger = get_logger("codeimpact.main")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensure every inbound HTTP request has a correlation ID for end-to-end tracing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        token = correlation_id_ctx.set(corr_id)
        start_time = time.time()
        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time
            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            return response
        finally:
            correlation_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    db_ok = await check_database_health()
    logger.info(
        f"Initial Database connectivity status: {'HEALTHY' if db_ok else 'UNAVAILABLE (will retry on demand)'}"
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Pull Request Change Risk Analysis and Test Selection Platform",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_origin_regex=r"^https?://.*(vercel\.app|netlify\.app|onrender\.com|localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health.router, prefix=settings.API_V1_STR)
app.include_router(repositories.router, prefix=settings.API_V1_STR)
app.include_router(pull_requests.router, prefix=settings.API_V1_STR)
app.include_router(analyses.router, prefix=settings.API_V1_STR)
app.include_router(predictions.router, prefix=settings.API_V1_STR)
app.include_router(tests.router, prefix=settings.API_V1_STR)
app.include_router(metrics.router, prefix=settings.API_V1_STR)
app.include_router(webhooks.router, prefix=settings.API_V1_STR)


@app.get("/docs", include_in_schema=False)
async def docs_redirect():
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=f"{settings.API_V1_STR}/docs")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "documentation": f"{settings.API_V1_STR}/docs",
        "health": f"{settings.API_V1_STR}/health",
    }
