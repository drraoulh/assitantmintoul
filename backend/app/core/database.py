from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session.

    Phase 1 chat does not persist messages. Wire this into routes
    once conversation history is stored in PostgreSQL.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_database() -> None:
    """Create tables if the database is enabled and reachable."""
    if not settings.database_enabled:
        return

    from app import models as _models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
