from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import AnalyticsEvent, Order, OrderLine, User
from ..schemas import AnalyticsEventCreate
from ..config import settings


async def record_event(
    db: AsyncSession,
    *,
    payload: AnalyticsEventCreate,
    user: Optional[User] = None,
) -> AnalyticsEvent:
    event = AnalyticsEvent(
        user_id=user.id if user else None,
        event_name=payload.event_name,
        source=payload.source,
        payload=json.dumps(payload.properties) if payload.properties else None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_events(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AnalyticsEvent], int]:
    stmt: Select[tuple[AnalyticsEvent]] = (
        select(AnalyticsEvent)
        .options(selectinload(AnalyticsEvent.user))
        .order_by(AnalyticsEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    count_stmt = select(func.count()).select_from(AnalyticsEvent)
    total = (await db.execute(count_stmt)).scalar_one()
    return events, total


async def build_sales_summary(
    db: AsyncSession,
    *,
    start: datetime,
    end: datetime,
) -> dict:
    start = start.replace(tzinfo=timezone.utc)
    end = end.replace(tzinfo=timezone.utc)

    totals_stmt = (
        select(
            func.count(func.distinct(Order.id)),
            func.coalesce(func.sum(Order.total_amount_cents), 0),
            func.coalesce(func.sum(Order.total_items), 0),
            func.avg(Order.total_amount_cents),
        )
        .where(Order.created_at >= start, Order.created_at < end)
    )
    total_orders, revenue, items, avg_order_value = (await db.execute(totals_stmt)).one()

    top_products_stmt = (
        select(
            OrderLine.product_id,
            func.max(OrderLine.product_title).label("product_title"),
            func.coalesce(func.sum(OrderLine.quantity), 0).label("units"),
            func.coalesce(func.sum(OrderLine.subtotal_cents), 0).label("revenue"),
        )
        .join(Order, Order.id == OrderLine.order_id)
        .where(Order.created_at >= start, Order.created_at < end)
        .group_by(OrderLine.product_id)
        .order_by(func.coalesce(func.sum(OrderLine.subtotal_cents), 0).desc())
        .limit(5)
    )
    top_rows = (await db.execute(top_products_stmt)).all()
    top_products = [
        {
            "product_id": row.product_id,
            "product_title": row.product_title,
            "units": int(row.units or 0),
            "revenue_cents": int(row.revenue or 0),
        }
        for row in top_rows
    ]

    return {
        "total_orders": int(total_orders or 0),
        "total_revenue_cents": int(revenue or 0),
        "total_items_sold": int(items or 0),
        "average_order_value_cents": int(avg_order_value or 0) if avg_order_value else 0,
        "top_products": top_products,
    }


def _bucket_expr(granularity: str):
    is_mysql = settings.database_url.startswith("mysql")
    if is_mysql:
        if granularity == "day":
            return func.date_format(Order.created_at, "%Y-%m-%d")
        if granularity == "week":
            # ISO-like week (year-week number)
            return func.date_format(Order.created_at, "%x-%v")
        if granularity == "month":
            return func.date_format(Order.created_at, "%Y-%m")
        return func.date_format(Order.created_at, "%Y-%m-%d")
    # SQLite / others fallback
    if granularity == "day":
        return func.strftime("%Y-%m-%d", Order.created_at)
    if granularity == "week":
        return func.strftime("%Y-%W", Order.created_at)
    if granularity == "month":
        return func.strftime("%Y-%m", Order.created_at)
    return func.strftime("%Y-%m-%d", Order.created_at)


async def build_sales_timeseries(
    db: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    granularity: str = "day",
) -> list[dict]:
    bucket = _bucket_expr(granularity)
    stmt = (
        select(
            bucket.label('bucket'),
            func.count(func.distinct(Order.id)).label('orders'),
            func.coalesce(func.sum(Order.total_amount_cents), 0).label('revenue_cents'),
            func.coalesce(func.sum(Order.total_items), 0).label('items'),
            func.avg(Order.total_amount_cents).label('aov'),
        )
        .where(Order.created_at >= start, Order.created_at < end)
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = (await db.execute(stmt)).all()
    points: list[dict] = []
    for row in rows:
        points.append({
            'bucket': row.bucket,
            'orders': int(row.orders or 0),
            'revenue_cents': int(row.revenue_cents or 0),
            'items': int(row.items or 0),
            'aov_cents': int(row.aov or 0) if row.aov else 0,
        })
    return points
