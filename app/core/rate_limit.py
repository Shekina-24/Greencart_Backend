from __future__ import annotations

import time
from typing import Optional, Tuple

from redis.asyncio import Redis

from app.config import settings

from .metrics import rate_limit_snapshot, record_rate_limit
from .redis import get_redis_client

_in_memory_store: dict[str, tuple[int, float]] = {}


def _resolve_rate_limit(namespace: str, limit: Optional[int], window: Optional[int]) -> Tuple[int, int]:
    default_limit, default_window = settings.rate_limit_rules.get(
        namespace, (settings.rate_limit_per_minute, 60)
    )
    final_limit = limit if limit is not None else default_limit
    final_window = window if window is not None else default_window
    return final_limit, final_window


async def check_rate_limit(
    key: str,
    *,
    namespace: str,
    limit: Optional[int] = None,
    window: Optional[int] = None,
) -> bool:
    limit_value, window_value = _resolve_rate_limit(namespace, limit, window)
    if limit_value <= 0:
        record_rate_limit(namespace, True)
        return True

    client: Optional[Redis] = get_redis_client()
    if client is not None:
        try:
            current = await client.incr(key)
            if current == 1:
                await client.expire(key, window_value)
            allowed = current <= limit_value
            record_rate_limit(namespace, allowed)
            return allowed
        except Exception:
            pass

    # Fallback in-memory bucket
    now = time.time()
    count, expires_at = _in_memory_store.get(key, (0, 0.0))
    if expires_at < now:
        count = 0
        expires_at = now + window_value
    count += 1
    _in_memory_store[key] = (count, expires_at)
    allowed = count <= limit_value
    record_rate_limit(namespace, allowed)
    return allowed


def rate_limit_metrics_snapshot() -> dict[str, dict[str, int]]:
    return rate_limit_snapshot()
