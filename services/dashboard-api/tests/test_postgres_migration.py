"""
Postgres migration smoke tests (ICD-7).

These tests run Alembic migrations against a real PostgreSQL instance and
verify the schema is correct after upgrade. They are SKIPPED unless the
DASHBOARD_POSTGRES_TEST_URL environment variable is set, so they do not
block the normal SQLite-backed CI run.

In GitHub Actions they are exercised by the `dashboard-api-postgres` job
which spins up a postgres:16 service container and sets this variable.

Tests:
- upgrade head succeeds and creates all expected tables
- downgrade base removes all tables cleanly
- upgrade is idempotent (running head twice is safe)
- ORM can write and read through the migrated schema
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

_PG_URL = os.environ.get("DASHBOARD_POSTGRES_TEST_URL", "")
_SKIP = not bool(_PG_URL)
_REASON = "DASHBOARD_POSTGRES_TEST_URL not set — postgres tests skipped"

_SERVICE_DIR = Path(__file__).resolve().parents[1]

# All tables created by migration 0001
_EXPECTED_TABLES = {
    "manifests",
    "assets",
    "campaigns",
    "campaign_manifests",
    "safe_mode_state",
    "audit_events",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_alembic(command: str) -> None:
    """Run an alembic command against the test postgres URL."""
    env = {**os.environ, "DASHBOARD_DATABASE_URL": _PG_URL}
    result = subprocess.run(
        ["python", "-m", "alembic", command],
        cwd=str(_SERVICE_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic {command} failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )


def _sync_table_names(conn) -> set[str]:
    """Return the set of table names visible in the current schema."""
    inspector = inspect(conn)
    return set(inspector.get_table_names())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="module")
async def pg_engine():
    """Create an async engine for the test postgres instance."""
    engine = create_async_engine(_PG_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def clean_schema(pg_engine):
    """
    Ensure a clean schema before each test.

    Runs downgrade to base (clears all tables), then runs upgrade head.
    """
    _run_alembic("downgrade base")
    _run_alembic("upgrade head")
    yield
    # Leave migrated schema in place — next test will clean up via downgrade


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_REASON)
def test_upgrade_head_succeeds():
    """alembic upgrade head completes without error."""
    _run_alembic("downgrade base")
    _run_alembic("upgrade head")


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_all_tables_created_after_upgrade(pg_engine):
    """All ICD-7 tables exist after upgrade head."""
    _run_alembic("downgrade base")
    _run_alembic("upgrade head")
    async with pg_engine.connect() as conn:
        tables = await conn.run_sync(_sync_table_names)
    assert _EXPECTED_TABLES.issubset(tables), (
        f"Missing tables after upgrade: {_EXPECTED_TABLES - tables}"
    )


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_downgrade_base_removes_all_tables(pg_engine):
    """alembic downgrade base removes all managed tables."""
    _run_alembic("upgrade head")
    _run_alembic("downgrade base")
    async with pg_engine.connect() as conn:
        tables = await conn.run_sync(_sync_table_names)
    # alembic_version may remain; our tables must all be gone
    remaining = _EXPECTED_TABLES & tables
    assert not remaining, f"Tables still present after downgrade base: {remaining}"


@pytest.mark.skipif(_SKIP, reason=_REASON)
def test_upgrade_head_idempotent():
    """Running upgrade head twice does not error."""
    _run_alembic("downgrade base")
    _run_alembic("upgrade head")
    _run_alembic("upgrade head")  # second run should be a no-op


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_safe_mode_singleton_seeded(pg_engine, clean_schema):
    """Migration seeds the safe_mode_state singleton row with id=1, is_active=false."""
    async with pg_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, is_active FROM safe_mode_state WHERE id = 1")
        )
        row = result.fetchone()
    assert row is not None, "safe_mode_state singleton row not found"
    assert row[0] == 1
    assert row[1] is False


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_manifests_indexes_exist(pg_engine, clean_schema):
    """Expected indexes on manifests table are created."""
    async with pg_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda c: {i["name"] for i in inspect(c).get_indexes("manifests")}
        )
    assert "ix_manifests_manifest_id" in indexes
    assert "ix_manifests_status" in indexes


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_audit_events_indexes_exist(pg_engine, clean_schema):
    """Expected indexes on audit_events table are created."""
    async with pg_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda c: {i["name"] for i in inspect(c).get_indexes("audit_events")}
        )
    assert "ix_audit_events_event_type" in indexes
    assert "ix_audit_events_entity_id" in indexes
    assert "ix_audit_events_created_at" in indexes


@pytest.mark.skipif(_SKIP, reason=_REASON)
@pytest.mark.asyncio
async def test_orm_write_read_roundtrip(pg_engine, clean_schema):
    """ORM can insert a manifest row and read it back via the migrated schema."""
    import uuid
    from datetime import datetime, timezone

    os.environ["DASHBOARD_DATABASE_URL"] = _PG_URL
    # Late import so the engine picks up the overridden URL
    from dashboard_api.models import ManifestModel  # noqa: PLC0415

    session_factory = async_sessionmaker(
        bind=pg_engine, expire_on_commit=False, class_=AsyncSession
    )
    manifest_id = f"test-pg-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    async with session_factory() as sess:
        async with sess.begin():
            m = ManifestModel(
                id=str(uuid.uuid4()),
                manifest_id=manifest_id,
                title="Postgres ORM smoke test",
                status="draft",
                schema_version="1.0.0",
                created_at=now,
                updated_at=now,
            )
            sess.add(m)

    async with session_factory() as sess:
        from sqlalchemy import select  # noqa: PLC0415
        from dashboard_api.models import ManifestModel as MM  # noqa: PLC0415
        result = await sess.execute(
            select(MM).where(MM.manifest_id == manifest_id)
        )
        row = result.scalar_one_or_none()

    assert row is not None, f"manifest_id={manifest_id} not found after insert"
    assert row.title == "Postgres ORM smoke test"
    assert row.status == "draft"
