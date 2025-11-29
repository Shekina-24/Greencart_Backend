from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import rate_limit
from app.schemas import AnalyticsReport, AnalyticsReportSummary, RateLimitMetrics, ReportFileInfo
from app.services import analytics as analytics_service
from app.services import audit as audit_service
from app.services import reports as reports_service

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"])


def _parse_datetime(value: str | None, *, default: datetime) -> datetime:
    if not value:
        return default
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime format") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/summary", response_model=AnalyticsReportSummary)
async def report_summary(
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
) -> AnalyticsReportSummary:
    end_default = datetime.now(timezone.utc)
    start_default = end_default - timedelta(days=30)
    start = _parse_datetime(period_start, default=start_default)
    end = _parse_datetime(period_end, default=end_default)
    summary = await analytics_service.build_sales_summary(db, start=start, end=end)
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="reports.summary",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"start": start.isoformat(), "end": end.isoformat()},
    )
    return AnalyticsReportSummary(
        period_start=start,
        period_end=end,
        **summary,
    )


@router.post("/generate", response_model=AnalyticsReport)
async def generate_report(
    request: Request,
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
    period_start: str | None = Query(default=None),
    period_end: str | None = Query(default=None),
) -> AnalyticsReport:
    end_default = datetime.now(timezone.utc)
    start_default = end_default - timedelta(days=30)
    start = _parse_datetime(period_start, default=start_default)
    end = _parse_datetime(period_end, default=end_default)
    summary = await analytics_service.build_sales_summary(db, start=start, end=end)

    artifacts = reports_service.generate_sales_report(summary, period_start=start, period_end=end)
    files = [
        ReportFileInfo(format=artifact.format, path=str(artifact.path), size_bytes=artifact.size_bytes)
        for artifact in artifacts
    ]
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="reports.generate",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "files": [str(artifact.path.name) for artifact in artifacts],
        },
    )
    return AnalyticsReport(
        summary=AnalyticsReportSummary(
            period_start=start,
            period_end=end,
            **summary,
        ),
        files=files,
    )


@router.get("/rate-limit-metrics", response_model=RateLimitMetrics)
async def get_rate_limit_metrics(
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> RateLimitMetrics:
    snapshot = rate_limit.rate_limit_metrics_snapshot()
    items = [
        {
            "namespace": namespace,
            "allowed": metrics.get("allowed", 0),
            "blocked": metrics.get("blocked", 0),
        }
        for namespace, metrics in snapshot.items()
    ]
    await audit_service.log_audit_event(
        db,
        user=current_admin,
        action="reports.rate_limit_metrics",
        metadata={"namespaces": list(snapshot.keys())},
    )
    return RateLimitMetrics(items=items)


@router.get("/files")
async def list_report_files(
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
) -> dict:
    storage = Path(reports_service._storage_directory())  # type: ignore[attr-defined]
    items = []
    for path in sorted(storage.glob("*")):
        if not path.is_file():
            continue
        fmt = path.suffix.lstrip(".").lower()
        items.append({
            "name": path.name,
            "format": fmt,
            "size_bytes": path.stat().st_size,
            "url": f"/reports/{path.name}",
        })
    return {"items": items}


@router.get("/download")
async def download_report_file(
    name: str = Query(..., description="Exact file name in reports storage"),
    db: AsyncSession = Depends(deps.get_db),
    current_admin=Depends(deps.get_current_admin),
):
    storage = Path(reports_service._storage_directory())  # type: ignore[attr-defined]
    # Prevent path traversal
    safe_name = Path(name).name
    file_path = storage / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), filename=safe_name)
