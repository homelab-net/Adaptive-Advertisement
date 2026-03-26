"""
Test fixtures for dashboard-api.

Uses SQLite (via aiosqlite) as the in-process test database — no PostgreSQL
required in CI.  All tables are created fresh per test session and cleared
between tests via transaction rollback.

Environment override: DASHBOARD_DATABASE_URL is set to the SQLite URL before
importing anything from dashboard_api so the engine is configured correctly.
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

# Override DB URL before any dashboard_api imports
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
os.environ["DASHBOARD_DATABASE_URL"] = _TEST_DB_URL


@pytest_asyncio.fixture
async def engine():
    pytest.importorskip(
        "aiosqlite",
        reason="dashboard-api tests require aiosqlite; install dashboard-api test extras",
    )
    from dashboard_api.models import Base

    eng = create_async_engine(
        _TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """
    Provide a clean AsyncSession per test.

    Uses a nested transaction (SAVEPOINT) so each test rolls back on exit,
    leaving the DB clean for the next test.
    """
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        async with sess.begin():
            yield sess
            await sess.rollback()


@pytest_asyncio.fixture
async def client(engine):
    """
    Async HTTP test client for the FastAPI application.

    Overrides the `get_session` dependency to use the test DB session.
    """
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session():
        async with factory() as sess:
            yield sess

    from dashboard_api.db import get_session
    from dashboard_api.main import create_app

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    httpx = pytest.importorskip(
        "httpx",
        reason="dashboard-api tests require httpx; install test extra dependencies to run this suite",
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
