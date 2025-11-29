import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    register_payload = {
        "email": "user@example.com",
        "password": "strongpass",
        "role": "consumer",
    }
    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 201, response.text

    login_payload = {
        "email": "user@example.com",
        "password": "strongpass"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
