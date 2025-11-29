from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Tuple

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Product, ProductImage, ProductStatus, ProducerProfile, User, UserRole
from ..schemas import ProductCreate, ProductUpdate


class ProductNotFoundError(Exception):
    """Raised when a product cannot be located."""


class ProductPermissionError(Exception):
    """Raised when a user lacks permissions to manage a product."""


VALID_SORTS = {
    "newest": Product.created_at.desc(),
    "oldest": Product.created_at.asc(),
    "price_asc": Product.price_cents.asc(),
    "price_desc": Product.price_cents.desc(),
    "impact_desc": Product.impact_co2_g.desc().nullslast(),
    "impact_asc": Product.impact_co2_g.asc().nullslast(),
}


async def list_products(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    q: str | None = None,
    category: str | None = None,
    region: str | None = None,
    status: ProductStatus | None = ProductStatus.PUBLISHED,
    dlc_within_days: int | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str = "newest",
) -> Tuple[list[Product], int]:
    sort_clause = VALID_SORTS.get(sort, VALID_SORTS["newest"])

    stmt: Select[tuple[Product]] = (
        select(Product)
        .options(selectinload(Product.images))
        .order_by(sort_clause, Product.id.desc())
        .limit(limit)
        .offset(offset)
    )

    count_stmt = select(func.count()).select_from(Product)

    filters = []
    if status:
        filters.append(Product.status == status)
        if status == ProductStatus.PUBLISHED:
            filters.append(Product.is_published.is_(True))
    if q:
        filters.append(Product.title.ilike(f"%{q}%"))
    if category:
        filters.append(Product.category == category)
    if region:
        filters.append(Product.region == region)
    if price_min is not None:
        filters.append(Product.price_cents >= price_min)
    if price_max is not None:
        filters.append(Product.price_cents <= price_max)
    if dlc_within_days is not None:
        end_date = date.today() + timedelta(days=dlc_within_days)
        filters.append(Product.dlc_date.isnot(None))
        filters.append(Product.dlc_date <= end_date)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    result = await db.execute(stmt)
    products = result.scalars().unique().all()

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    return products, total


async def get_product(
    db: AsyncSession,
    product_id: int,
    *,
    include_unpublished: bool = False,
) -> Product | None:
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    if not include_unpublished:
        stmt = stmt.where(Product.is_published.is_(True), Product.status == ProductStatus.PUBLISHED)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_product(
    db: AsyncSession,
    *,
    producer: User,
    product_in: ProductCreate,
) -> Product:
    if producer.role not in {UserRole.PRODUCER, UserRole.ADMIN}:
        raise ProductPermissionError("Producer or admin role required")

    stmt = (
        select(ProducerProfile.id)
        .where(ProducerProfile.user_id == producer.id)
        .limit(1)
    )
    result = await db.execute(stmt)
    producer_profile_id = result.scalar_one_or_none()

    product = Product(
        producer_id=producer.id,
        producer_profile_id=producer_profile_id,
        title=product_in.title,
        description=product_in.description,
        category=product_in.category,
        region=product_in.region,
        origin=product_in.origin,
        dlc_date=product_in.dlc_date,
        impact_co2_g=product_in.impact_co2_g,
        price_cents=product_in.price_cents,
        promo_price_cents=product_in.promo_price_cents,
        stock=product_in.stock,
        status=product_in.status,
        is_published=product_in.is_published,
    )

    _assign_images(product, product_in.images)

    db.add(product)
    await db.commit()
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product.id)
    )
    return result.scalar_one()


async def update_product(
    db: AsyncSession,
    *,
    product: Product,
    payload: ProductUpdate,
) -> Product:
    if payload.title is not None:
        product.title = payload.title
    if payload.description is not None:
        product.description = payload.description
    if payload.category is not None:
        product.category = payload.category
    if payload.region is not None:
        product.region = payload.region
    if payload.origin is not None:
        product.origin = payload.origin
    if payload.dlc_date is not None:
        product.dlc_date = payload.dlc_date
    if payload.impact_co2_g is not None:
        product.impact_co2_g = payload.impact_co2_g
    if payload.price_cents is not None:
        product.price_cents = payload.price_cents
    if payload.promo_price_cents is not None:
        product.promo_price_cents = payload.promo_price_cents
    if payload.stock is not None:
        product.stock = payload.stock
    if payload.status is not None:
        product.status = payload.status
    if payload.is_published is not None:
        product.is_published = payload.is_published
    if payload.images is not None:
        product.images.clear()
        _assign_images(product, payload.images)

    await db.commit()
    await db.refresh(product)
    return product


def _assign_images(product: Product, images: Iterable) -> None:
    for idx, image in enumerate(images):
        product.images.append(
            ProductImage(
                url=str(image.url),
                is_primary=image.is_primary or idx == 0,
            )
        )


async def list_products_for_producer(
    db: AsyncSession,
    *,
    producer: User,
    limit: int,
    offset: int,
) -> Tuple[list[Product], int]:
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.producer_id == producer.id)
        .order_by(Product.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    products = result.scalars().unique().all()

    count_stmt = (
        select(func.count())
        .select_from(Product)
        .where(Product.producer_id == producer.id)
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return products, total


async def get_product_for_producer(
    db: AsyncSession,
    *,
    producer: User,
    product_id: int,
) -> Product | None:
    stmt = (
        select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id, Product.producer_id == producer.id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_product(
    db: AsyncSession,
    *,
    product: Product,
) -> None:
    await db.delete(product)
    await db.commit()
