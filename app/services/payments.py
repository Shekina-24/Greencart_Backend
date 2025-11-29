from __future__ import annotations

from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order, OrderStatus
from ..schemas import PaymentInitRequest, PaymentSession, PaymentWebhookPayload
from . import orders as orders_service
from ..config import settings

try:
    import stripe  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    stripe = None


class PaymentProviderError(Exception):
    """Raised when payment provider interaction fails."""


async def init_payment_session(
    db: AsyncSession,
    *,
    order: Order,
    request: PaymentInitRequest,
) -> PaymentSession:
    if order.status not in {OrderStatus.PENDING, OrderStatus.DRAFT}:
        raise PaymentProviderError("Order already processed")

    provider = request.provider.lower()
    if provider == "stripe":
        if stripe is None or not settings.stripe_secret_key:
            raise PaymentProviderError("Stripe not configured")
        # Configure Stripe
        stripe.api_key = settings.stripe_secret_key

        # Build line items from order lines
        line_items = [
            {
                "price_data": {
                    "currency": (order.currency or "EUR").lower(),
                    "product_data": {"name": line.product_title},
                    "unit_amount": int(line.unit_price_cents),
                },
                "quantity": int(line.quantity),
            }
            for line in order.lines
        ]

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=line_items,
                success_url=f"{request.success_url}?order={order.id}&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{request.cancel_url}?order={order.id}",
                client_reference_id=str(order.id),
                metadata={"order_id": str(order.id)},
            )
        except Exception as exc:  # pragma: no cover - external call
            raise PaymentProviderError(f"Stripe error: {exc}") from exc

        order.payment_provider = provider
        order.payment_reference = session.get("id")
        await db.commit()
        await db.refresh(order)

        checkout_url = session.get("url")
        if not checkout_url:
            raise PaymentProviderError("Stripe session missing URL")
        return PaymentSession(checkout_url=checkout_url, payment_reference=order.payment_reference)

    # Default: sandbox/manual placeholder
    order.payment_provider = provider
    order.payment_reference = f"{provider}_session_{order.id}"
    await db.commit()
    await db.refresh(order)

    checkout_url = f"https://checkout.{provider}.sandbox/session/{order.payment_reference}"
    return PaymentSession(checkout_url=checkout_url, payment_reference=order.payment_reference)


async def handle_webhook(
    db: AsyncSession,
    *,
    data: PaymentWebhookPayload,
) -> Tuple[Order, OrderStatus]:
    order = await orders_service.get_order_by_id(db, order_id=data.order_id)
    if order is None:
        raise PaymentProviderError("Order not found")
    if order.payment_provider != data.provider:
        raise PaymentProviderError("Provider mismatch")

    event = data.event
    if event == "payment_succeeded":
        await orders_service.update_order_status(
            db,
            order=order,
            status=OrderStatus.PAID,
            reference=data.payload.get("payment_intent", order.payment_reference),
        )
    elif event == "payment_failed":
        await orders_service.update_order_status(db, order=order, status=OrderStatus.CANCELLED)
    elif event == "payment_refunded":
        await orders_service.update_order_status(db, order=order, status=OrderStatus.REFUNDED)
    else:
        raise PaymentProviderError("Unknown event")

    return order, order.status


async def handle_stripe_event(db: AsyncSession, *, event: dict) -> Tuple[Order, OrderStatus]:
    """Handle a Stripe webhook event and update the corresponding order.

    Expects the Checkout Session to include client_reference_id or metadata.order_id.
    """
    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}

    # Identify order id from metadata or client reference
    order_id = None
    metadata = obj.get("metadata") or {}
    if "order_id" in metadata:
        try:
            order_id = int(metadata["order_id"])  # type: ignore[arg-type]
        except Exception:
            order_id = None
    if order_id is None and obj.get("client_reference_id"):
        try:
            order_id = int(obj.get("client_reference_id"))
        except Exception:
            order_id = None

    if order_id is None:
        raise PaymentProviderError("Stripe webhook missing order reference")

    order = await orders_service.get_order_by_id(db, order_id=order_id)
    if order is None:
        raise PaymentProviderError("Order not found")

    if event_type == "checkout.session.completed":
        reference = obj.get("payment_intent") or obj.get("id")
        updated = await orders_service.update_order_status(
            db,
            order=order,
            status=OrderStatus.PAID,
            reference=str(reference) if reference else None,
        )
        return updated, updated.status
    if event_type in {"charge.refunded", "payment_intent.canceled"}:
        updated = await orders_service.update_order_status(db, order=order, status=OrderStatus.REFUNDED)
        return updated, updated.status
    if event_type in {"checkout.session.expired", "payment_intent.payment_failed"}:
        updated = await orders_service.update_order_status(db, order=order, status=OrderStatus.CANCELLED)
        return updated, updated.status

    raise PaymentProviderError(f"Unhandled Stripe event: {event_type}")
