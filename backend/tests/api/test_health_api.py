"""Tests for health check and readiness probe endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_readiness(client: AsyncClient):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "database" in data
