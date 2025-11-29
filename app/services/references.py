from __future__ import annotations

from typing import Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReferenceKind, ReferenceValue
from ..schemas import ReferenceValueCreate, ReferenceValueUpdate


async def list_reference_values(
    db: AsyncSession,
    *,
    kind: ReferenceKind,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[list[ReferenceValue], int]:
    stmt = (
        select(ReferenceValue)
        .where(ReferenceValue.kind == kind)
        .order_by(ReferenceValue.name.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    count_stmt = select(func.count()).select_from(ReferenceValue).where(ReferenceValue.kind == kind)
    total = (await db.execute(count_stmt)).scalar_one()
    return items, total


async def create_reference_value(
    db: AsyncSession,
    *,
    kind: ReferenceKind,
    payload: ReferenceValueCreate,
) -> ReferenceValue:
    item = ReferenceValue(
        kind=kind,
        name=payload.name,
        slug=payload.slug,
        is_active=payload.is_active,
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("Reference already exists") from exc
    await db.refresh(item)
    return item


async def update_reference_value(
    db: AsyncSession,
    *,
    item: ReferenceValue,
    payload: ReferenceValueUpdate,
) -> ReferenceValue:
    if payload.name is not None:
        item.name = payload.name
    if payload.slug is not None:
        item.slug = payload.slug
    if payload.is_active is not None:
        item.is_active = payload.is_active

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("Reference already exists") from exc
    await db.refresh(item)
    return item


async def delete_reference_value(db: AsyncSession, *, item: ReferenceValue) -> None:
    await db.delete(item)
    await db.commit()


async def get_reference_value(db: AsyncSession, *, kind: ReferenceKind, value_id: int) -> ReferenceValue | None:
    stmt = select(ReferenceValue).where(ReferenceValue.id == value_id, ReferenceValue.kind == kind)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
