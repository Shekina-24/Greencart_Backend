from __future__ import annotations

from functools import lru_cache
from typing import Optional

from redis.asyncio import Redis

from app.config import settings


@lru_cache(maxsize=1)
def get_redis_client() -> Optional[Redis]:
    url = settings.redis_url
    if not url:
        return None
    return Redis.from_url(url, decode_responses=True)
