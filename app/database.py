from __future__ import annotations

from collections.abc import AsyncIterator
import asyncio
import logging
import ssl

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# =====================================================
# Engine
# =====================================================

_engine_kwargs: dict = {
    "echo": settings.debug,
    "future": True,
    "pool_pre_ping": True,  # drop dead connections before use
    "pool_recycle": 1800,   # recycle connections to avoid server/proxy timeouts
}

# --- SSL context (IMPORTANT): aiomysql needs an SSLContext, not a dict.
_ssl_ctx = None
if settings.database_url.startswith("mysql"):
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE  # accept self-signed certs (Railway/proxy)

if _ssl_ctx is not None:
    _engine_kwargs["connect_args"] = {"ssl": _ssl_ctx}

if settings.database_url.startswith("mysql"):
    # Small pool for hosted MySQL to avoid long waits on dead sockets
    _engine_kwargs.update(pool_size=5, max_overflow=5, pool_timeout=30)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# SQLite specific pragma (if you ever switch to sqlite locally)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# =====================================================
# Session dependency
# =====================================================

async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a SQLAlchemy async session."""
    async with AsyncSessionLocal() as session:
        yield session


# =====================================================
# Init / Health checks
# =====================================================

async def db_ping() -> bool:
    """Return True if DB responds, else False."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("DB ping failed")
        return False


async def init_db(*, timeout_seconds: int = 5) -> None:
    """
    Initialize database schema (create tables).
    IMPORTANT:
    - Do NOT call this blindly in production startup.
    - Use a flag (ENV var) and keep a short timeout.
    """
    # Import models so Base.metadata is populated
    import app.models  # noqa: F401

    async def _work():
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)

    try:
        await asyncio.wait_for(_work(), timeout=timeout_seconds)
        logger.info("DB init OK (tables created/verified).")
    except asyncio.TimeoutError:
        logger.warning("DB init timeout after %ss (startup continues).", timeout_seconds)
    except Exception:
        # Don't crash the whole API because DB init failed
        logger.exception("DB init failed (startup continues).")

print("DATABASE_URL =", settings.database_url)
