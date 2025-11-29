from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User, UserRole
from app.services import analytics as analytics_service
from app.services import reports as reports_service
from app.services import email as email_service

logger = logging.getLogger(__name__)


def _last_full_month(now: datetime) -> tuple[datetime, datetime]:
    first_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    end = first_of_month  # exclusive
    start = (first_of_month - timedelta(days=1)).replace(day=1)
    return start, end


async def _list_recipients(db) -> list[str]:
    stmt = select(User.email).where(
        User.is_active.is_(True),
        User.email.is_not(None),
        User.role.in_([UserRole.ADMIN, UserRole.PRODUCER]),
    )
    result = await db.execute(stmt)
    emails = [row[0] for row in result.all() if row[0]]
    return sorted(set(emails))


async def run_monthly_sales_report(now: datetime | None = None) -> None:
    """
    Generate previous month's sales report and email links to admins/producers.
    Safe to call from a scheduler; uses its own DB session.
    """
    if not settings.enable_monthly_reports:
        logger.info("Monthly reports disabled; skipping job")
        return
    current = now or datetime.now(timezone.utc)
    period_start, period_end = _last_full_month(current)

    async with AsyncSessionLocal() as db:
        summary = await analytics_service.build_sales_summary(db, start=period_start, end=period_end)
        artifacts = reports_service.generate_sales_report(summary, period_start=period_start, period_end=period_end)
        links = [f"{settings.api_v1_str}/../reports/{artifact.path.name}" for artifact in artifacts]
        recipients = await _list_recipients(db)

    if not recipients:
        logger.info("Monthly report generated but no recipients found")
        return

    subject = f"[{settings.project_name}] Rapport mensuel {period_start.strftime('%Y-%m')}"
    lines = [
        f"Période : {period_start:%d/%m/%Y} -> {period_end:%d/%m/%Y}",
        f"Total commandes : {summary.get('total_orders')}",
        f"Revenu total (centimes) : {summary.get('total_revenue_cents')}",
        f"Articles vendus : {summary.get('total_items_sold')}",
        f"Panier moyen (centimes) : {summary.get('average_order_value_cents')}",
        "",
        "Fichiers :",
        *[f"- {link}" for link in links],
    ]
    body = "\n".join(lines)

    for recipient in recipients:
        try:
            await email_service.send_email(
                to=recipient,
                subject=subject,
                body=body,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send monthly report to %s: %s", recipient, exc)

    logger.info("Monthly report sent to %s recipients", len(recipients))
