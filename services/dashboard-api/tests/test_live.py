"""
Tests for GET /api/v1/live — real-time CV pipeline and player state snapshot.

Strategy:
- All tests use the in-memory SQLite test DB (via the shared `client` fixture).
- Player /healthz is mocked at the aiohttp layer so no real TCP connection is made.
- Tests verify the shape and correctness of the response under various DB states.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from httpx import AsyncClient

from dashboard_api.models import AudienceSnapshot, PlayEvent, SafeModeState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(delta_s: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=delta_s)


def _fresh_snapshot(**kwargs) -> AudienceSnapshot:
    defaults = dict(
        id="snap-1",
        sampled_at=_utc(-5),       # 5 s old — well within 30 s threshold
        presence_count=3,
        presence_confidence=0.91,
        state_stable=True,
        pipeline_degraded=False,
        demographics_suppressed=True,
        age_group_child=None,
        age_group_young_adult=None,
        age_group_adult=None,
        age_group_senior=None,
    )
    defaults.update(kwargs)
    return AudienceSnapshot(**defaults)


def _play_event(**kwargs) -> PlayEvent:
    defaults = dict(
        id="pe-1",
        manifest_id="manifest-alpha",
        activated_at=_utc(-30),
        reason="young_adult",
        prev_manifest_id=None,
    )
    defaults.update(kwargs)
    return PlayEvent(**defaults)


def _mock_player_probe(healthy: bool):
    """Return a context manager patch that fakes the player /healthz probe."""
    from dashboard_api.schemas import ServiceProbe
    probe = ServiceProbe(
        status="healthy" if healthy else "unreachable",
        probed_at=datetime.now(timezone.utc),
    )

    async def _fake_probe(*args, **kwargs):
        return probe

    return patch(
        "dashboard_api.routers.system._probe_service",
        new=AsyncMock(side_effect=_fake_probe),
    )


# ---------------------------------------------------------------------------
# No data — empty DB
# ---------------------------------------------------------------------------

class TestLiveNoData:
    async def test_returns_200(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            resp = await client.get("/api/v1/live")
        assert resp.status_code == 200

    async def test_cv_unavailable_when_no_snapshot(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()
        assert data["cv"]["available"] is False

    async def test_cv_fields_null_when_no_snapshot(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()
        cv = data["cv"]
        assert cv["count"] is None
        assert cv["confidence"] is None
        assert cv["signal_age_ms"] is None

    async def test_player_unavailable_when_probe_fails(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()
        assert data["player"]["available"] is False
        assert data["player"]["state"] is None


# ---------------------------------------------------------------------------
# CV snapshot present and fresh
# ---------------------------------------------------------------------------

class TestLiveFreshSnapshot:
    @pytest.fixture(autouse=True)
    async def seed_snapshot(self, session):
        session.add(_fresh_snapshot())
        # Note: session fixture rolls back after each test

    async def test_cv_available(self, client: AsyncClient, session):
        # Snapshot seeded via autouse seed_snapshot fixture (session fixture rolls back).
        # This test verifies the endpoint is reachable; deeper assertions are in test_cv_available_true.
        with _mock_player_probe(healthy=True):
            resp = await client.get("/api/v1/live")
        assert resp.status_code == 200

        # Simpler: just hit the endpoint with its real session and seeded data
        # The client fixture uses a separate session factory; seed via client's session.
        # Since conftest uses per-test transactions we seed differently here.

    async def test_cv_available_true(self, client: AsyncClient, engine):
        """Seed snapshot directly into the DB and verify available=true."""
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            s.add(_fresh_snapshot(id="snap-fresh-1"))
            await s.commit()

        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()

        assert data["cv"]["available"] is True
        assert data["cv"]["count"] == 3
        assert data["cv"]["confidence"] == pytest.approx(0.91)
        assert data["cv"]["state_stable"] is True
        assert data["cv"]["freeze_decision"] is False
        assert data["cv"]["signal_age_ms"] is not None
        assert data["cv"]["signal_age_ms"] < 30_000

    async def test_cv_demographics_suppressed(self, client: AsyncClient, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            s.add(_fresh_snapshot(id="snap-sup-1", demographics_suppressed=True))
            await s.commit()

        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()

        assert data["cv"]["demographics"]["suppressed"] is True
        assert data["cv"]["demographics"]["age_group"] is None

    async def test_cv_demographics_available(self, client: AsyncClient, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            s.add(_fresh_snapshot(
                id="snap-demo-1",
                demographics_suppressed=False,
                age_group_child=0.1,
                age_group_young_adult=0.5,
                age_group_adult=0.35,
                age_group_senior=0.05,
            ))
            await s.commit()

        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()

        demo = data["cv"]["demographics"]
        assert demo["suppressed"] is False
        assert demo["age_group"]["child"] == pytest.approx(0.1)
        assert demo["age_group"]["young_adult"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Stale snapshot (> 30 s old)
# ---------------------------------------------------------------------------

class TestLiveStaleSnapshot:
    async def test_cv_unavailable_when_stale(self, client: AsyncClient, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            s.add(_fresh_snapshot(id="snap-stale-1", sampled_at=_utc(-60)))  # 60 s ago
            await s.commit()

        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()

        assert data["cv"]["available"] is False
        # Data is still returned even when stale — just marked unavailable
        assert data["cv"]["signal_age_ms"] >= 30_000


# ---------------------------------------------------------------------------
# Player state inference
# ---------------------------------------------------------------------------

class TestLivePlayerState:
    async def _seed_play_event(self, engine, **kwargs):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            s.add(_play_event(**kwargs))
            await s.commit()

    async def test_player_active_when_healthy_and_play_event(self, client, engine):
        await self._seed_play_event(engine, id="pe-active-1")
        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()
        assert data["player"]["available"] is True
        assert data["player"]["state"] == "active"
        assert data["player"]["active_manifest_id"] == "manifest-alpha"

    async def test_player_fallback_when_healthy_no_play_event(self, client, engine):
        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()
        assert data["player"]["state"] == "fallback"

    async def test_player_safe_mode_when_engaged(self, client, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as s:
            await s.merge(SafeModeState(
                id=1,
                is_active=True,
                reason="operator override",
                activated_at=_utc(),
                activated_by="ops",
            ))
            await s.commit()

        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()

        assert data["player"]["state"] == "safe_mode"
        assert data["player"]["safe_mode_reason"] == "operator override"

        # Cleanup safe mode for subsequent tests
        async with factory() as s:
            await s.merge(SafeModeState(id=1, is_active=False))
            await s.commit()

    async def test_player_safe_mode_reason_null_when_not_active(self, client, engine):
        with _mock_player_probe(healthy=True):
            data = (await client.get("/api/v1/live")).json()
        assert data["player"]["safe_mode_reason"] is None


# ---------------------------------------------------------------------------
# Response schema completeness
# ---------------------------------------------------------------------------

class TestLiveResponseSchema:
    async def test_top_level_keys(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            data = (await client.get("/api/v1/live")).json()
        assert "cv" in data
        assert "player" in data

    async def test_cv_keys_present(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            cv = (await client.get("/api/v1/live")).json()["cv"]
        for key in ("available", "count", "confidence", "fps", "inference_ms",
                    "signal_age_ms", "state_stable", "freeze_decision", "demographics"):
            assert key in cv, f"missing key: {key}"

    async def test_player_keys_present(self, client: AsyncClient):
        with _mock_player_probe(healthy=False):
            player = (await client.get("/api/v1/live")).json()["player"]
        for key in ("available", "state", "active_manifest_id",
                    "dwell_elapsed", "freeze_reason", "safe_mode_reason"):
            assert key in player, f"missing key: {key}"

    async def test_fps_and_inference_ms_null(self, client: AsyncClient):
        """These fields are not yet persisted in the DB."""
        with _mock_player_probe(healthy=False):
            cv = (await client.get("/api/v1/live")).json()["cv"]
        assert cv["fps"] is None
        assert cv["inference_ms"] is None
