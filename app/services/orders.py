from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple
from uuid import uuid4

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Order, OrderLine, OrderStatus, Product, ProductStatus, Review, ReviewStatus, User
from ..schemas import OrderCreate


class OrderValidationError(Exception):
    """Raised when an order payload is invalid."""


class ProductUnavailableError(Exception):
    """Raised when a requested product is missing or unpublished."""


class OutOfStockError(Exception):
    """Raised when product stock is insufficient."""


async def list_orders(
    db: AsyncSession,
    *,
    user: User,
    limit: int,
    offset: int,
) -> Tuple[list[Order], int]:
    stmt: Select[tuple[Order]] = (
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    orders = result.scalars().unique().all()

    count_stmt = select(func.count()).select_from(Order).where(Order.user_id == user.id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    return orders, total


async def get_order(db: AsyncSession, *, user: User, order_id: int) -> Order | None:
    stmt = (
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.id == order_id, Order.user_id == user.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_order(
    db: AsyncSession,
    *,
    user: User,
    order_in: OrderCreate,
    idempotency_key: str,
    payment_provider: str | None = None,
) -> Tuple[Order, bool]:
    if not idempotency_key:
        raise OrderValidationError("Idempotency-Key header is required")
    if idempotency_key.strip() == "":
        raise OrderValidationError("Idempotency-Key header is required")
    if idempotency_key == "{{$uuid}}":
        idempotency_key = uuid4().hex

    existing_stmt = (
        select(Order)
        .options(selectinload(Order.lines))
        .where(Order.user_id == user.id, Order.idempotency_key == idempotency_key)
    )
    existing_result = await db.execute(existing_stmt)
    existing_order = existing_result.scalar_one_or_none()
    if existing_order:
        return existing_order, False

    product_ids = {item.product_id for item in order_in.items}
    if not product_ids:
        raise OrderValidationError("Order requires at least one product")

    products_stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id.in_(product_ids))
    )
    products_result = await db.execute(products_stmt)
    products = {product.id: product for product in products_result.scalars().all()}

    missing_ids = product_ids - products.keys()
    if missing_ids:
        raise ProductUnavailableError(f"Products not found: {sorted(missing_ids)}")

    for item in order_in.items:
        product = products[item.product_id]
        if product.status != ProductStatus.PUBLISHED or not product.is_published:
            raise ProductUnavailableError(f"Product {product.id} is not available for purchase")
        if product.stock < item.quantity:
            raise OutOfStockError(f"Product {product.id} has insufficient stock")

    order = Order(
        user_id=user.id,
        status=OrderStatus.PENDING,
        currency="EUR",
        total_amount_cents=0,
        total_items=0,
        total_impact_co2_g=0,
        idempotency_key=idempotency_key,
        placed_at=datetime.now(timezone.utc),
    )
    if payment_provider:
        order.payment_provider = payment_provider
    db.add(order)

    for item in order_in.items:
        product = products[item.product_id]
        sale_price = product.promo_price_cents if product.promo_price_cents is not None else product.price_cents
        reference_price = product.price_cents if product.promo_price_cents is not None else None
        subtotal = sale_price * item.quantity
        co2 = (product.impact_co2_g or 0) * item.quantity

        order.lines.append(
            OrderLine(
                product_id=product.id,
                product_title=product.title,
                quantity=item.quantity,
                unit_price_cents=sale_price,
                reference_price_cents=reference_price if reference_price is not None else product.price_cents,
                subtotal_cents=subtotal,
                impact_co2_g=co2 if co2 else None,
            )
        )
        order.total_amount_cents += subtotal
        order.total_items += item.quantity
        order.total_impact_co2_g += co2

        product.stock -= item.quantity

    order.notes = order_in.notes

    await db.commit()

    refreshed_result = await db.execute(
        select(Order).options(selectinload(Order.lines)).where(Order.id == order.id)
    )
    return refreshed_result.scalar_one(), True


async def get_order_by_id(db: AsyncSession, *, order_id: int) -> Order | None:
    stmt = select(Order).options(selectinload(Order.lines)).where(Order.id == order_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession,
    *,
    order: Order,
    status: OrderStatus,
    reference: str | None = None,
) -> Order:
    order.status = status
    if reference:
        order.payment_reference = reference
    await db.commit()
    await db.refresh(order)
    return order


async def list_orders_for_producer(
    db: AsyncSession,
    *,
    producer: User,
    limit: int,
    offset: int,
) -> Tuple[list[Order], int]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.lines).selectinload(OrderLine.product),
            selectinload(Order.user),
        )
        .join(Order.lines)
        .join(OrderLine.product)
        .where(Product.producer_id == producer.id)
        .order_by(Order.created_at.desc())
        .distinct()
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    orders = result.scalars().unique().all()

    count_stmt = (
        select(func.count(func.distinct(Order.id)))
        .join(Order.lines)
        .join(OrderLine.product)
        .where(Product.producer_id == producer.id)
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return orders, total


async def compute_producer_insights(
    db: AsyncSession,
    *,
    producer: User,
) -> dict:
    totals_stmt = (
        select(
            func.count(func.distinct(Order.id)),
            func.coalesce(func.sum(OrderLine.subtotal_cents), 0),
            func.coalesce(func.sum(OrderLine.quantity), 0),
            func.coalesce(func.sum(OrderLine.impact_co2_g), 0),
        )
        .join(Order.lines)
        .join(OrderLine.product)
        .where(Product.producer_id == producer.id)
    )
    total_orders, total_revenue, total_items, total_co2 = (await db.execute(totals_stmt)).one()

    total_orders = int(total_orders or 0)
    total_revenue = int(total_revenue or 0)
    total_items = int(total_items or 0)
    total_co2 = int(total_co2 or 0)
    avg_order_value = int(total_revenue / total_orders) if total_orders else 0

    top_stmt = (
        select(
            OrderLine.product_id,
            Product.title,
            func.coalesce(func.sum(OrderLine.subtotal_cents), 0).label('revenue'),
            func.coalesce(func.sum(OrderLine.quantity), 0).label('units'),
            func.avg(Review.rating).label('avg_rating'),
        )
        .join(Product, Product.id == OrderLine.product_id)
        .join(Order, Order.id == OrderLine.order_id)
        .outerjoin(
            Review,
            and_(Review.product_id == OrderLine.product_id, Review.status == ReviewStatus.APPROVED),
        )
        .where(Product.producer_id == producer.id)
        .group_by(OrderLine.product_id, Product.title)
        .order_by(func.coalesce(func.sum(OrderLine.subtotal_cents), 0).desc())
        .limit(5)
    )
    top_rows = (await db.execute(top_stmt)).all()
    top_products = []
    for row in top_rows:
        avg_rating = float(row.avg_rating) if row.avg_rating is not None else None
        top_products.append(
            {
                'product_id': row.product_id,
                'title': row.title,
                'revenue_cents': int(row.revenue) if row.revenue else 0,
                'units_sold': int(row.units) if row.units else 0,
                'average_rating': avg_rating,
            }
        )

    return {
        'total_orders': total_orders,
        'total_revenue_cents': total_revenue,
        'total_items_sold': total_items,
        'average_order_value_cents': avg_order_value,
        'total_impact_co2_g': total_co2,
        'top_products': top_products,
    }
