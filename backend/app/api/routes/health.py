from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_database_health
from app.workers.queue import task_queue

router = APIRouter(tags=["Health"])


@router.get("/health", summary="System Health & Readiness Probe")
async def get_health() -> JSONResponse:
    """
    Returns the real-time operational status of CodeImpact backend,
    checking relational database connectivity and Redis queue responsiveness.
    """
    db_healthy = await check_database_health()
    redis_healthy = task_queue.check_redis_health()

    is_healthy = db_healthy and redis_healthy
    overall_status = (
        "ok" if is_healthy else ("degraded" if (db_healthy or redis_healthy) else "unhealthy")
    )

    response_payload = {
        "status": overall_status,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {
            "database": {
                "status": "connected" if db_healthy else "disconnected",
                "type": "postgresql",
            },
            "redis": {
                "status": "connected" if redis_healthy else "disconnected",
                "queue": settings.REDIS_QUEUE_NAME,
            },
        },
    }

    status_code = (
        status.HTTP_200_OK if overall_status != "unhealthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=response_payload)
