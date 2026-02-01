from collections.abc import AsyncIterator
import ssl

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# --- SSL context (IMPORTANT): uvloop/aiomysql needs an SSLContext, not a dict.
_ssl_ctx = None
if settings.database_url.startswith("mysql"):
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE  # accept self-signed certs


_engine_kwargs: dict = {
    "echo": settings.debug,
    "future": True,
    "pool_pre_ping": True,  # drop dead connections before use
    "pool_recycle": 1800,   # recycle connections to avoid server/proxy timeouts
}

if _ssl_ctx is not None:
    _engine_kwargs["connect_args"] = {"ssl": _ssl_ctx}

if settings.database_url.startswith("mysql"):
    # Keep the pool small for hosted MySQL and avoid long waits on dead sockets.
    _engine_kwargs.update(pool_size=5, max_overflow=5, pool_timeout=30)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a SQLAlchemy async session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create database tables on application startup."""
    import app.models  # noqa: F401

    # Optional: quick ping before create_all to fail fast with a clearer error
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.run_sync(Base.metadata.create_all)
