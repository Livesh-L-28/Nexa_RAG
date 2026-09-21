"""API tests for registration, authentication, and profile retrieval."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "email": "newuser@nexarag.ai",
        "password": "strongpassword123",
        "role": "USER",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@nexarag.ai"
    assert data["role"] == "USER"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "anotherpassword123",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "password123",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user):
    payload = {
        "email": test_user.email,
        "password": "wrongpassword!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, test_user, user_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
