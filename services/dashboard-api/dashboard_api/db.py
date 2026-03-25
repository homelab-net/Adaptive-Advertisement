"""
Async SQLAlchemy engine and session factory (ICD-7).

Usage
-----
Depend on `get_session` in FastAPI route handlers:

    async def my_route(session: AsyncSession = Depends(get_session)):
        ...

The engine is created once at import time.  Call `init_db()` at startup to
create all tables (development / test only — production uses Alembic).
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings
from .models import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one session per request, auto-closed."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """
    Create all tables from the ORM metadata.

    Use in development and tests only.
    Production deploys use `alembic upgrade head`.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all tables — for test teardown only."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
