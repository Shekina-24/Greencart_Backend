from __future__ import annotations

from collections import defaultdict
from typing import Dict

_rate_limit_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"allowed": 0, "blocked": 0})


def record_rate_limit(namespace: str, allowed: bool) -> None:
    stats = _rate_limit_stats[namespace]
    if allowed:
        stats["allowed"] += 1
    else:
        stats["blocked"] += 1


def rate_limit_snapshot() -> Dict[str, Dict[str, int]]:
    return {namespace: dict(values) for namespace, values in _rate_limit_stats.items()}
