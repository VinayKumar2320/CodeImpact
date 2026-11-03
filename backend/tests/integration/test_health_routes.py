from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient):
    with (
        patch("app.api.routes.health.check_database_health", return_value=True),
        patch("app.api.routes.health.task_queue.check_redis_health", return_value=True),
    ):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "CodeImpact"
        assert data["components"]["database"]["status"] == "connected"
        assert data["components"]["redis"]["status"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_degraded(client: AsyncClient):
    with (
        patch("app.api.routes.health.check_database_health", return_value=True),
        patch("app.api.routes.health.task_queue.check_redis_health", return_value=False),
    ):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["status"] == "connected"
        assert data["components"]["redis"]["status"] == "disconnected"


@pytest.mark.asyncio
async def test_health_endpoint_unhealthy(client: AsyncClient):
    with (
        patch("app.api.routes.health.check_database_health", return_value=False),
        patch("app.api.routes.health.task_queue.check_redis_health", return_value=False),
    ):
        response = await client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_correlation_id_middleware(client: AsyncClient):
    custom_id = "test-corr-id-12345"
    response = await client.get("/api/v1/health", headers={"X-Correlation-ID": custom_id})
    assert response.headers.get("X-Correlation-ID") == custom_id
    assert "X-Process-Time" in response.headers
