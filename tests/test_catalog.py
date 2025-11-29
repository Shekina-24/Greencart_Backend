import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_products_as_public(client: AsyncClient):
    response = await client.get("/api/v1/products")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
