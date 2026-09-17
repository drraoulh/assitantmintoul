import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


settings = get_settings()

_LOCAL_HOSTS = ("@localhost", "@127.0.0.1", "@postgres:", "@db:")


def _is_local(url: str) -> bool:
    return any(host in url for host in _LOCAL_HOSTS)


def _uses_pgbouncer(url: str) -> bool:
    """Supabase's pooler (transaction :6543 or session :5432) runs pgbouncer."""
    return "pooler.supabase.com" in url or ":6543" in url


def _engine_options(url: str) -> dict[str, Any]:
    connect_args: dict[str, Any] = {}
    if not _is_local(url):
        # Managed Postgres (Supabase) only accepts TLS connections.
        connect_args["ssl"] = "require"

    options: dict[str, Any] = {"connect_args": connect_args, "pool_pre_ping": True}
    if _uses_pgbouncer(url):
        # Disable asyncpg prepared-statement caches for pgbouncer compatibility.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
        options["poolclass"] = NullPool
        options.pop("pool_pre_ping")
    return options


engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True,
    **_engine_options(settings.database_url),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_database() -> bool:
    """Create tables if the database is enabled and reachable.

    Never raises: an unreachable database must not stop the API, the chat
    simply falls back to in-memory history.
    """
    if not settings.database_enabled:
        return False

    from app import models as _models  # noqa: F401

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001 - startup must stay resilient
        logger.warning(
            "Database unavailable (%s). Conversations stay in memory. "
            "Check DATABASE_URL / Supabase credentials.",
            exc,
        )
        return False

    logger.info("Conversation history persisted to the configured database.")
    return True
