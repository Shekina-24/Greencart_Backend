import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_reviews_requires_auth(client: AsyncClient):
    payload = {
        "product_id": 1,
        "rating": 5,
    }
    response = await client.post("/api/v1/reviews", json=payload)
    assert response.status_code in {401, 400}
