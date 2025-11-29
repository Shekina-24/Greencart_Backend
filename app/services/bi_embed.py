from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from ..config import settings

logger = logging.getLogger(__name__)


def _with_filters(embed_url: str, filters: dict[str, Any]) -> str:
  """Append non-null filters as query params to the embed URL."""
  parsed = urlparse(embed_url)
  existing = dict(parse_qsl(parsed.query))
  for key, value in filters.items():
    if value is None:
      continue
    existing[key] = str(value)
  new_query = urlencode(existing, doseq=True)
  return urlunparse(parsed._replace(query=new_query))


async def issue_powerbi_embed_token(
  *,
  region: Optional[str],
  producer_id: Optional[int],
  date_start: Optional[str],
  date_end: Optional[str],
  client_ip: Optional[str],
  user_agent: Optional[str],
) -> dict:
  """Return embed payload using a pre-provisioned token (service principal handled upstream)."""
  if not settings.powerbi_embed_url:
    raise RuntimeError("Power BI embed URL is not configured")
  if not settings.powerbi_static_token:
    raise RuntimeError("Power BI embed token is not configured")

  filters = {
    "region": region,
    "producer_id": producer_id,
    "date_start": date_start,
    "date_end": date_end,
  }
  filtered_url = _with_filters(settings.powerbi_embed_url, filters)
  expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.powerbi_token_ttl_seconds)

  logger.info(
    "Issuing Power BI embed token",
    extra={
      "region": region,
      "producer_id": producer_id,
      "date_start": date_start,
      "date_end": date_end,
      "client_ip": client_ip,
      "user_agent": user_agent,
      "timeout_seconds": settings.powerbi_token_ttl_seconds,
    },
  )

  return {
    "embed_url": filtered_url,
    "token": settings.powerbi_static_token,
    "expires_at": expires_at,
  }
