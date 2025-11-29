from datetime import datetime, timedelta, timezone

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.schemas import (
    AnalyticsEventCreate,
    AnalyticsEmbedTokenRequest,
    AnalyticsEmbedTokenResponse,
    AnalyticsEventListResponse,
    AnalyticsEventRead,
    AnalyticsReportSummary,
    AnalyticsTimeseries,
)
from app.services import analytics as analytics_service
from app.services import bi_embed

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)


@router.post("/events", response_model=AnalyticsEventRead, status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(
    request: Request,
    payload: AnalyticsEventCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_optional_user),
) -> AnalyticsEventRead:
    await deps.enforce_ip_rate_limit(request, prefix="analytics")
    event = await analytics_service.record_event(
        db,
        payload=payload,
        user=current_user,
    )
    return AnalyticsEventRead.model_validate(event)


@router.get("/events", response_model=AnalyticsEventListResponse)
async def list_events(
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ) -> AnalyticsEventListResponse:
    events, total = await analytics_service.list_events(db, limit=limit, offset=offset)
    return AnalyticsEventListResponse(
        items=[AnalyticsEventRead.model_validate(event) for event in events],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=AnalyticsReportSummary)
async def public_sales_summary(
    db: AsyncSession = Depends(deps.get_db),
) -> AnalyticsReportSummary:
    """Expose a rolling 30-day sales summary for public landing page banners."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    summary = await analytics_service.build_sales_summary(db, start=start, end=end)
    return AnalyticsReportSummary(
        period_start=start,
        period_end=end,
        **summary,
    )


@router.get("/timeseries", response_model=AnalyticsTimeseries)
async def sales_timeseries(
    db: AsyncSession = Depends(deps.get_db),
    period_start: str | None = None,
    period_end: str | None = None,
    granularity: str = "day",
) -> AnalyticsTimeseries:
    end = datetime.now(timezone.utc) if not period_end else datetime.fromisoformat(period_end)
    start = end - timedelta(days=30) if not period_start else datetime.fromisoformat(period_start)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    points = await analytics_service.build_sales_timeseries(db, start=start, end=end, granularity=granularity)
    return AnalyticsTimeseries(points=points)


@router.post("/embed-token", response_model=AnalyticsEmbedTokenResponse, status_code=status.HTTP_201_CREATED)
async def issue_embed_token(
    request: Request,
    payload: AnalyticsEmbedTokenRequest,
    current_admin=Depends(deps.get_current_admin),
) -> AnalyticsEmbedTokenResponse:
    await deps.enforce_ip_rate_limit(request, prefix="analytics_embed")
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        result = await bi_embed.issue_powerbi_embed_token(
            region=payload.region,
            producer_id=payload.producer_id,
            date_start=payload.date_start,
            date_end=payload.date_end,
            client_ip=client_ip,
            user_agent=user_agent,
        )
    except RuntimeError as exc:
        logger.warning("Failed to issue embed token: %s", exc, extra={"client_ip": client_ip, "user_agent": user_agent})
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return AnalyticsEmbedTokenResponse.model_validate(result)
