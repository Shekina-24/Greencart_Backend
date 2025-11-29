from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import Select, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Order, OrderLine, OrderStatus, Review, ReviewStatus, User
from ..schemas import ReviewCreate, ReviewModerationRequest


class ReviewPermissionError(Exception):
    """Raised when the user cannot post a review."""


async def list_product_reviews(
    db: AsyncSession,
    *,
    product_id: int,
    status: ReviewStatus = ReviewStatus.APPROVED,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[list[Review], int]:
    # MySQL ne supporte pas NULLS LAST ; on émule en triant d'abord sur le flag "is null".
    published_null_last = case((Review.published_at.is_(None), 1), else_=0).asc()
    stmt: Select[tuple[Review]] = (
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.product_id == product_id, Review.status == status)
        .order_by(published_null_last, Review.published_at.desc(), Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    reviews = result.scalars().all()

    count_stmt = select(func.count()).select_from(Review).where(
        Review.product_id == product_id,
        Review.status == status,
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return reviews, total


async def create_review(
    db: AsyncSession,
    *,
    user: User,
    payload: ReviewCreate,
) -> Review:
    order_stmt = (
        select(Order)
        .join(Order.lines)
        .where(
            Order.user_id == user.id,
            # Autoriser aussi les commandes en attente (PENDING) pour simplifier la phase MVP
            Order.status.in_([OrderStatus.PAID, OrderStatus.COMPLETED, OrderStatus.PENDING]),
            OrderLine.product_id == payload.product_id,
        )
        .order_by(Order.created_at.desc())
    )
    order_result = await db.execute(order_stmt)
    order = order_result.scalars().first()
    if not order:
        raise ReviewPermissionError("No completed purchase found for this product")

    review = Review(
        user_id=user.id,
        product_id=payload.product_id,
        order_id=payload.order_id or order.id,
        rating=payload.rating,
        comment=payload.comment,
        status=ReviewStatus.PENDING,
    )
    db.add(review)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ReviewPermissionError("Review already submitted") from exc

    await db.refresh(review)
    return review


async def update_review(
    db: AsyncSession,
    *,
    review: Review,
    user: User,
    payload: ReviewCreate,
) -> Review:
    # Only author or admin can edit
    if user.id != review.user_id and getattr(user.role, "name", str(user.role)) != 'ADMIN' and str(user.role).lower() != 'admin':
        raise ReviewPermissionError("Not allowed to edit this review")
    # Ensure product consistency
    if payload.product_id != review.product_id:
        raise ReviewPermissionError("Product mismatch")
    review.rating = payload.rating
    review.comment = payload.comment
    # Reset to pending on edit
    review.status = ReviewStatus.PENDING
    review.published_at = None
    await db.commit()
    await db.refresh(review)
    return review


async def delete_review(
    db: AsyncSession,
    *,
    review: Review,
    user: User,
) -> None:
    if user.id != review.user_id and getattr(user.role, "name", str(user.role)) != 'ADMIN' and str(user.role).lower() != 'admin':
        raise ReviewPermissionError("Not allowed to delete this review")
    await db.delete(review)
    await db.commit()


async def list_reviews_for_moderation(
    db: AsyncSession,
    *,
    status: ReviewStatus = ReviewStatus.PENDING,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[list[Review], int]:
    stmt = (
        select(Review)
        .options(selectinload(Review.user), selectinload(Review.product))
        .where(Review.status == status)
        .order_by(Review.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    reviews = result.scalars().all()

    count_stmt = select(func.count()).select_from(Review).where(Review.status == status)
    total = (await db.execute(count_stmt)).scalar_one()
    return reviews, total


async def moderate_review(
    db: AsyncSession,
    *,
    review: Review,
    payload: ReviewModerationRequest,
) -> Review:
    review.status = payload.status
    review.published_at = datetime.now(timezone.utc) if payload.status == ReviewStatus.APPROVED else None
    review.moderation_notes = payload.moderation_notes

    await db.commit()
    await db.refresh(review)
    return review


async def get_review(db: AsyncSession, review_id: int) -> Review | None:
    stmt = select(Review).where(Review.id == review_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_reviews_for_user(
    db: AsyncSession,
    *,
    user: User,
    limit: int = 20,
    offset: int = 0,
) -> Tuple[list[Review], int]:
    stmt = (
        select(Review)
        .options(selectinload(Review.product))
        .where(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    reviews = result.scalars().all()

    count_stmt = select(func.count()).select_from(Review).where(Review.user_id == user.id)
    total = (await db.execute(count_stmt)).scalar_one()
    return reviews, total
