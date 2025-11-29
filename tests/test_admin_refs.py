import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_refs_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/admin/refs/category")
    assert response.status_code == 401
