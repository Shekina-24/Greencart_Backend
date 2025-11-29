from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import CartItem, Product, ProductStatus, User
from ..schemas import CartItemUpdate


class CartEmptyError(Exception):
    """Raised when cart operation expects items but none provided."""


class CartStockError(Exception):
    """Raised when requested quantity infringes stock."""


async def get_cart(
    db: AsyncSession,
    user: User,
) -> Tuple[List[CartItem], int, int]:
    stmt: Select[tuple[CartItem]] = (
        select(CartItem)
        .options(selectinload(CartItem.product))
        .where(CartItem.user_id == user.id)
        .order_by(CartItem.created_at.asc())
    )

    result = await db.execute(stmt)
    items = result.scalars().all()
    total_items = sum(item.quantity for item in items)
    total_amount = sum(item.quantity * item.unit_price_cents for item in items)
    return items, total_items, total_amount


async def set_cart_items(
    db: AsyncSession,
    *,
    user: User,
    updates: List[CartItemUpdate],
) -> Tuple[List[CartItem], int, int]:
    if not updates:
        await clear_cart(db, user=user)
        return await get_cart(db, user)

    product_ids = {update.product_id for update in updates}
    products_stmt = (
        select(Product)
        .where(Product.id.in_(product_ids), Product.status == ProductStatus.PUBLISHED, Product.is_published.is_(True))
    )
    products_result = await db.execute(products_stmt)
    products: Dict[int, Product] = {product.id: product for product in products_result.scalars()}

    missing = product_ids - products.keys()
    if missing:
        raise CartStockError(f"Produit(s) introuvable(s): {sorted(missing)}")

    for update in updates:
        product = products[update.product_id]
        if update.quantity > product.stock:
            raise CartStockError(f"Stock insuffisant pour le produit {product.id}")

    existing_stmt = select(CartItem).where(CartItem.user_id == user.id)
    existing_result = await db.execute(existing_stmt)
    existing_items: Dict[int, CartItem] = {
        item.product_id: item for item in existing_result.scalars().all()
    }

    for update in updates:
        product = products[update.product_id]
        if update.quantity == 0:
            if update.product_id in existing_items:
                await db.delete(existing_items[update.product_id])
            continue

        item = existing_items.get(update.product_id)
        sale_price = int(product.promo_price_cents) if product.promo_price_cents is not None else int(product.price_cents)
        if item is None:
            item = CartItem(
                user_id=user.id,
                product_id=product.id,
                quantity=update.quantity,
                unit_price_cents=sale_price,
                product_title=product.title,
            )
            db.add(item)
        else:
            item.quantity = update.quantity
            item.unit_price_cents = sale_price
            item.product_title = product.title

    await db.commit()
    return await get_cart(db, user=user)


async def clear_cart(db: AsyncSession, *, user: User) -> None:
    stmt = select(CartItem).where(CartItem.user_id == user.id)
    result = await db.execute(stmt)
    items = result.scalars().all()
    for item in items:
        await db.delete(item)
    await db.commit()
