from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RefreshToken, User
from ..schemas import RefreshTokenPayload


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ensure_aware(dt: Union[datetime, None]) -> Union[datetime, None]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def store_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    token: str,
    payload: RefreshTokenPayload,
    user_agent: Optional[str],
    ip_address: Optional[str],
) -> RefreshToken:
    hashed = _hash_token(token)
    record = RefreshToken(
        user_id=user.id,
        jti=payload.jti,
        hashed_token=hashed,
        expires_at=datetime.fromtimestamp(payload.exp, tz=timezone.utc),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def validate_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    token: str,
    payload: RefreshTokenPayload,
) -> RefreshToken:
    hashed = _hash_token(token)
    stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.jti == payload.jti,
        )
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        raise ValueError("Refresh token not found")
    revoked_at = _ensure_aware(record.revoked_at)
    if revoked_at is not None:
        raise ValueError("Refresh token revoked")
    expires_at = _ensure_aware(record.expires_at)
    if expires_at is not None and expires_at < datetime.now(timezone.utc):
        raise ValueError("Refresh token expired")
    if record.hashed_token != hashed:
        raise ValueError("Refresh token mismatch")
    return record


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    user: User,
    old_record: RefreshToken,
    new_token: str,
    new_payload: RefreshTokenPayload,
    user_agent: Optional[str],
    ip_address: Optional[str],
) -> RefreshToken:
    old_record.revoked_at = datetime.now(timezone.utc)
    hashed = _hash_token(new_token)
    new_record = RefreshToken(
        user_id=user.id,
        jti=new_payload.jti,
        hashed_token=hashed,
        expires_at=datetime.fromtimestamp(new_payload.exp, tz=timezone.utc),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record
