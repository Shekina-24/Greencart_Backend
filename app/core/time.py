from __future__ import annotations
from datetime import datetime, timezone

def utcnow() -> datetime:
    # UTC aware + arrondi à la seconde (évite microsecondes aléatoires)
    return datetime.now(timezone.utc).replace(microsecond=0)

def to_utc_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    # si dt est naive (pas de tz), on la considère UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")
