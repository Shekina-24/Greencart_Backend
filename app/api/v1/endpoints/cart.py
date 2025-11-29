from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import CartItemRead, CartItemUpdate, CartRead
from app.services import cart as cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartRead)
async def get_my_cart(
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_consumer),
) -> CartRead:
    items, total_items, total_amount = await cart_service.get_cart(db, current_user)
    return CartRead(
        items=[
            CartItemRead(
                id=item.id,
                product_id=item.product_id,
                product_title=item.product_title,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                subtotal_cents=item.quantity * item.unit_price_cents,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total_items=total_items,
        total_amount_cents=total_amount,
    )


@router.put("", response_model=CartRead)
async def upsert_cart(
    payload: List[CartItemUpdate],
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_consumer),
) -> CartRead:
    try:
        items, total_items, total_amount = await cart_service.set_cart_items(
            db,
            user=current_user,
            updates=payload,
        )
    except cart_service.CartStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return CartRead(
        items=[
            CartItemRead(
                id=item.id,
                product_id=item.product_id,
                product_title=item.product_title,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                subtotal_cents=item.quantity * item.unit_price_cents,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total_items=total_items,
        total_amount_cents=total_amount,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_consumer),
) -> None:
    await cart_service.clear_cart(db, user=current_user)
