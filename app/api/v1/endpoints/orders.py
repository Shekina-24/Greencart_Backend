import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import OrderCreate, OrderListResponse, OrderRead
from app.services import cart as cart_service
from app.services import email as email_service
from app.services import orders as orders_service
from app.services.email import EmailSendError

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    response: Response,
    db: AsyncSession = Depends(deps.get_db),
    current_consumer=Depends(deps.get_current_consumer),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> OrderRead:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    try:
        order, created = await orders_service.create_order(
            db,
            user=current_consumer,
            order_in=payload,
            idempotency_key=idempotency_key,
            payment_provider="manual",
        )
    except orders_service.ProductUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except orders_service.OutOfStockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except orders_service.OrderValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not created:
        response.status_code = status.HTTP_200_OK
    else:
        await cart_service.clear_cart(db, user=current_consumer)
        try:
            line_payloads = [
                {
                    "quantity": line.quantity,
                    "title": line.product_title,
                    "amount": email_service.format_currency(line.subtotal_cents, order.currency),
                }
                for line in order.lines
            ]
            await email_service.send_order_confirmation_email(
                to=current_consumer.email,
                first_name=current_consumer.first_name,
                locale=getattr(current_consumer, "locale", None),
                order_id=order.id,
                order_date=order.created_at,
                total_amount_cents=order.total_amount_cents,
                currency=order.currency,
                lines=line_payloads,
            )
        except EmailSendError as exc:
            logger.warning("Order confirmation email failed for order %s: %s", order.id, exc)

    return OrderRead.model_validate(order)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_consumer=Depends(deps.get_current_consumer),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OrderListResponse:
    orders, total = await orders_service.list_orders(
        db,
        user=current_consumer,
        limit=limit,
        offset=offset,
    )
    return OrderListResponse(
        items=[OrderRead.model_validate(order) for order in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_consumer=Depends(deps.get_current_consumer),
) -> OrderRead:
    order = await orders_service.get_order(db, user=current_consumer, order_id=order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return OrderRead.model_validate(order)
