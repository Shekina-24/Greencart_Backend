from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Iterable, Optional

import requests

from app.config import settings
from . import templates

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(Exception):
    """Raised when email configuration is missing."""


class EmailSendError(Exception):
    """Raised when an email cannot be sent."""


def _resolve_locale(locale: Optional[str]) -> str:
    return (locale or settings.email_default_locale or "fr").lower()


def format_currency(amount_cents: int, currency: str = "EUR") -> str:
    amount = amount_cents / 100
    if currency.upper() == "EUR":
        return f"{amount:,.2f} €".replace(",", " ").replace(".", ",")
    return f"{amount:,.2f} {currency}"


def _email_is_enabled() -> bool:
    # Coupe-circuit global : en dev on ne veut jamais casser le flux à cause de l’email.
    return bool(getattr(settings, "email_enabled", False))


async def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    subtype: str = "plain",
) -> None:
    # ✅ 1) Coupe-circuit global
    if not _email_is_enabled():
        logger.info("Email disabled; skipping send_email(to=%s, subject=%s)", to, subject)
        return

    # ✅ 2) Vérification config Mailjet
    if not settings.mailjet_api_key or not settings.mailjet_api_secret:
        # En prod, c'est une erreur de config. En dev, on passe déjà par le coupe-circuit.
        raise EmailNotConfiguredError("Mailjet API settings missing")

    from_email = settings.mailjet_from_email or settings.email_sender
    if not from_email:
        raise EmailNotConfiguredError("Sender email missing (MAILJET_FROM_EMAIL or EMAIL_SENDER)")

    payload = {
        "Messages": [
            {
                "From": {
                    "Email": from_email,
                    "Name": settings.mailjet_from_name or settings.project_name,
                },
                "To": [{"Email": to}],
                "Subject": subject,
            }
        ]
    }
    if subtype.lower() == "html":
        payload["Messages"][0]["HTMLPart"] = body
    else:
        payload["Messages"][0]["TextPart"] = body

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            _send_via_mailjet,
            payload,
            settings.mailjet_api_key,
            settings.mailjet_api_secret,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send email to %s", to)
        raise EmailSendError("Failed to send email") from exc


async def send_templated_email(
    template_name: str,
    *,
    to: str,
    locale: Optional[str] = None,
    context: Optional[dict] = None,
) -> None:
    # ✅ Coupe-circuit global avant même les templates
    if not _email_is_enabled():
        logger.info("Email disabled; skipping send_templated_email(template=%s, to=%s)", template_name, to)
        return

    resolved_locale = _resolve_locale(locale)
    final_context = {"project_name": settings.project_name}
    if context:
        final_context.update(context)

    try:
        subject, body = templates.render_email_content(
            template_name,
            locale=resolved_locale,
            context=final_context,
        )
    except (templates.TemplateNotFoundError, ValueError) as exc:
        logger.exception(
            "Email template '%s' missing/invalid for locale '%s'",
            template_name,
            resolved_locale,
        )
        raise EmailSendError("Email template unavailable") from exc

    # Par défaut, tes templates sont sûrement du HTML. Si tu sais que c'est du texte, laisse "plain".
    await send_email(to=to, subject=subject, body=body, subtype="html")


async def send_welcome_email(
    *,
    to: str,
    first_name: Optional[str],
    locale: Optional[str] = None,
) -> None:
    await send_templated_email(
        "welcome",
        to=to,
        locale=locale,
        context={"first_name": first_name or settings.project_name},
    )


async def send_order_confirmation_email(
    *,
    to: str,
    first_name: Optional[str],
    locale: Optional[str],
    order_id: int,
    order_date: datetime,
    total_amount_cents: int,
    currency: str,
    lines: Iterable[dict[str, str]],
) -> None:
    line_messages = [f"- {item['quantity']} x {item['title']} ({item['amount']})" for item in lines]
    await send_templated_email(
        "order_confirmation",
        to=to,
        locale=locale,
        context={
            "first_name": first_name or settings.project_name,
            "order_id": order_id,
            "order_date": order_date.strftime("%d/%m/%Y"),
            "total_amount": format_currency(total_amount_cents, currency),
            "order_lines": "\n".join(line_messages),
        },
    )


def _send_blocking(
    message,
    host: str,
    port: int,
    username: Optional[str],
    password: Optional[str],
    timeout_seconds: int | float,
) -> None:
    raise NotImplementedError("SMTP sending is no longer used; this should not be called.")


def _send_via_mailjet(payload: dict, api_key: str, api_secret: str) -> None:
    resp = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(api_key, api_secret),
        json=payload,
        timeout=20,
    )
    if resp.status_code >= 400:
        raise EmailSendError(f"Mailjet API error {resp.status_code}: {resp.text}")
    data = resp.json()
    messages = data.get("Messages", [])
    if not messages or messages[0].get("Status") != "success":
        raise EmailSendError(f"Mailjet send failed: {resp.text}")
