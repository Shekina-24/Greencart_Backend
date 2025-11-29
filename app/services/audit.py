from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog, User


async def log_audit_event(
    db: AsyncSession,
    *,
    user: Optional[User],
    action: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        actor_role=user.role.value if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        details=None if metadata is None else str(metadata),
    )
    db.add(log)
    await db.commit()
