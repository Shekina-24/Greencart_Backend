from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .api.v1.api import api_router
from .config import settings
from .database import init_db
from .jobs.monthly_reports import run_monthly_sales_report

@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()

    scheduler = AsyncIOScheduler(timezone="UTC")
    if settings.enable_monthly_reports:
        scheduler.add_job(
            run_monthly_sales_report,
            CronTrigger(day=1, hour=settings.monthly_report_hour_utc, minute=0),
            name="monthly_sales_report",
        )
        scheduler.start()

    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins= "https://greencartfrontend-six.vercel.app",
    #allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_str)

# Ensure the static directory exists (for uploaded images)
_BASE_DIR = Path(__file__).resolve().parent.parent  # project root (greencart_backend)
_STATIC_DIR = _BASE_DIR / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Mount generated reports for download (read-only)
_REPORTS_DIR = _BASE_DIR / "generated_reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(_REPORTS_DIR)), name="reports")
