import asyncio
from logging.config import fileConfig
from typing import Final

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import settings
from app.database import Base

import app.models  # noqa: F401  # ensure models are imported

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

ASYNC_URL: Final[str] = settings.database_url


def _sync_url(async_url: str) -> str:
    if async_url.startswith("sqlite+aiosqlite"):
        return async_url.replace("sqlite+aiosqlite", "sqlite", 1)
    if async_url.startswith("postgresql+asyncpg"):
        return async_url.replace("postgresql+asyncpg", "postgresql", 1)
    if async_url.startswith("mysql+aiomysql"):
        return async_url.replace("mysql+aiomysql", "mysql+pymysql", 1)
    if async_url.startswith("mysql+asyncmy"):
        return async_url.replace("mysql+asyncmy", "mysql+pymysql", 1)
    return async_url


config.set_main_option("sqlalchemy.url", _sync_url(ASYNC_URL))


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(ASYNC_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(
        ASYNC_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
