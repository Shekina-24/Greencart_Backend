from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Order, OrderLine, Review, User


async def export_user_data(db: AsyncSession, user: User) -> Dict[str, Any]:
    user_data = {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "region": user.region,
            "consent_newsletter": user.consent_newsletter,
            "consent_analytics": user.consent_analytics,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }
    }

    orders_stmt = (
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    orders_result = await db.execute(orders_stmt)
    orders = []
    for order in orders_result.scalars().all():
        orders.append(
            {
                "id": order.id,
                "status": order.status.value,
                "total_amount_cents": order.total_amount_cents,
                "created_at": order.created_at.isoformat(),
                "lines": [
                    {
                        "product_id": line.product_id,
                        "product_title": line.product_title,
                        "quantity": line.quantity,
                        "unit_price_cents": line.unit_price_cents,
                    }
                    for line in order.lines
                ],
            }
        )
    user_data["orders"] = orders

    reviews_stmt = select(Review).where(Review.user_id == user.id)
    reviews_result = await db.execute(reviews_stmt)
    user_data["reviews"] = [
        {
            "id": review.id,
            "product_id": review.product_id,
            "rating": review.rating,
            "comment": review.comment,
            "status": review.status.value,
            "created_at": review.created_at.isoformat(),
        }
        for review in reviews_result.scalars().all()
    ]
    return user_data


async def erase_user_data(db: AsyncSession, user: User) -> None:
    user_id = user.id

    await db.execute(delete(Order).where(Order.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
