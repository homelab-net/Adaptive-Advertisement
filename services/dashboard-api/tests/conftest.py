"""
Test fixtures for dashboard-api.

Uses SQLite (via aiosqlite) as the in-process test database — no PostgreSQL
required in CI.  All tables are created fresh per test session and cleared
between tests via transaction rollback.

Environment override: DASHBOARD_DATABASE_URL is set to the SQLite URL before
importing anything from dashboard_api so the engine is configured correctly.
"""
import os
import importlib.util
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

_MISSING_TEST_DEPS = [
    dep for dep in ("httpx", "aiosqlite")
    if importlib.util.find_spec(dep) is None
]


def _skip_if_missing_test_deps() -> None:
    if _MISSING_TEST_DEPS:
        pytest.skip(
            "dashboard-api tests require optional deps: "
            + ", ".join(sorted(_MISSING_TEST_DEPS)),
            allow_module_level=False,
        )

# Override DB URL before any dashboard_api imports
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
os.environ["DASHBOARD_DATABASE_URL"] = _TEST_DB_URL

if _MISSING_TEST_DEPS:
    create_app = None
    Base = None
    get_session = None
else:
    from dashboard_api.main import create_app  # noqa: E402
    from dashboard_api.models import Base  # noqa: E402
    from dashboard_api.db import get_session  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    _skip_if_missing_test_deps()
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
    _skip_if_missing_test_deps()
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
    _skip_if_missing_test_deps()
    """
    Async HTTP test client for the FastAPI application.

    Overrides the `get_session` dependency to use the test DB session.
    """
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_session():
        async with factory() as sess:
            yield sess

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
