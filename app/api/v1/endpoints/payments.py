from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import PaymentInitRequest, PaymentSession, PaymentWebhookPayload
from app.services import orders as orders_service
from app.services import payments as payments_service
from app.config import settings

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    stripe = None

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/init", response_model=PaymentSession)
async def init_payment(
    payload: PaymentInitRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_consumer),
) -> PaymentSession:
    order = await orders_service.get_order(db, user=current_user, order_id=payload.order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    try:
        session = await payments_service.init_payment_session(db, order=order, request=payload)
    except payments_service.PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return session


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def payment_webhook(
    payload: PaymentWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
) -> dict[str, str]:
    signature = request.headers.get("X-Payment-Signature")
    if not signature or signature != payload.signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    try:
        order, status_updated = await payments_service.handle_webhook(db, data=payload)
    except payments_service.PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"status": status_updated.value, "order_id": str(order.id)}


@router.post("/stripe/webhook", status_code=status.HTTP_202_ACCEPTED)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(deps.get_db)) -> dict[str, str]:
    if stripe is None or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Stripe not configured")

    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature")

    payload = await request.body()
    try:  # pragma: no cover - external lib
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=signature, secret=settings.stripe_webhook_secret
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook: {exc}") from exc

    try:
        order, status_updated = await payments_service.handle_stripe_event(db, event=event)
    except payments_service.PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"status": status_updated.value, "order_id": str(order.id)}
