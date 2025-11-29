from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import hash_password, verify_password
from ..models import ProducerProfile, ProducerStatus, User, UserRole
from ..schemas import UserCreate, UserUpdate


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user with an email already stored."""


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    existing = await get_user_by_email(db, user_in.email)
    if existing:
        raise UserAlreadyExistsError("Email already registered")

    user = User(
        email=user_in.email.lower(),
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        region=user_in.region,
        consent_newsletter=user_in.consent_newsletter,
        consent_analytics=user_in.consent_analytics,
        is_active=True,
    )

    if user.role == UserRole.PRODUCER and user.producer_profile is None:
        user.producer_profile = ProducerProfile(status=ProducerStatus.PENDING)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def touch_last_login(db: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()


async def update_user(db: AsyncSession, user: User, payload: UserUpdate) -> User:
    if payload.first_name is not None:
        user.first_name = payload.first_name
    if payload.last_name is not None:
        user.last_name = payload.last_name
    if payload.region is not None:
        user.region = payload.region
    if payload.consent_newsletter is not None:
        user.consent_newsletter = payload.consent_newsletter
    if payload.consent_analytics is not None:
        user.consent_analytics = payload.consent_analytics

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def set_user_role(db: AsyncSession, *, user: User, role: UserRole) -> User:
    user.role = role
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    items = result.scalars().all()
    from sqlalchemy import func as sa_func
    total_stmt = select(sa_func.count()).select_from(User)
    total = (await db.execute(total_stmt)).scalar_one()
    return items, int(total or 0)


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.commit()
