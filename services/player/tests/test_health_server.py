"""
Health server endpoint tests for the player service.

Tests /healthz, /readyz, /control/safe-mode (POST/DELETE), and /metrics.
OBS-002, OBS-003, ICD-8.

Uses aiohttp's TestClient — no renderer, no decision-optimizer WS server needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from player.health import make_health_app
from player.state import StateMachine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def ready_client(aiohttp_client):
    sm = StateMachine()
    is_ready = [True]
    on_transition_holder = [AsyncMock()]
    app = await make_health_app(sm, is_ready, on_transition_holder)
    return await aiohttp_client(app)


@pytest.fixture
async def not_ready_client(aiohttp_client):
    sm = StateMachine()
    is_ready = [False]
    on_transition_holder = [None]
    app = await make_health_app(sm, is_ready, on_transition_holder)
    return await aiohttp_client(app)


# ── /healthz ─────────────────────────────────────────────────────────────────

class TestHealthz:
    async def test_200_always(self, ready_client):
        resp = await ready_client.get("/healthz")
        assert resp.status == 200

    async def test_body_status_ok(self, ready_client):
        body = await (await ready_client.get("/healthz")).json()
        assert body["status"] == "ok"

    async def test_200_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/healthz")
        assert resp.status == 200


# ── /readyz ───────────────────────────────────────────────────────────────────

class TestReadyz:
    async def test_200_when_ready(self, ready_client):
        resp = await ready_client.get("/readyz")
        assert resp.status == 200

    async def test_body_status_ok(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert body["status"] == "ok"

    async def test_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/readyz")
        assert resp.status == 503

    async def test_503_body_reason(self, not_ready_client):
        body = await (await not_ready_client.get("/readyz")).json()
        assert body["status"] == "not_ready"
        assert "reason" in body


# ── /control/safe-mode (ICD-8) ───────────────────────────────────────────────

class TestSafeModeControl:
    async def test_post_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.post(
            "/control/safe-mode",
            json={"reason": "operator_manual"},
        )
        assert resp.status == 503

    async def test_delete_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.delete("/control/safe-mode")
        assert resp.status == 503

    async def test_post_engage_200_when_ready(self, ready_client):
        resp = await ready_client.post(
            "/control/safe-mode",
            json={"reason": "operator_manual"},
        )
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
        assert "state" in body

    async def test_post_engage_supervisor_escalation(self, ready_client):
        resp = await ready_client.post(
            "/control/safe-mode",
            json={"reason": "supervisor_escalation"},
        )
        assert resp.status == 200

    async def test_post_engage_unknown_reason_falls_back_to_manual(self, ready_client):
        """Unknown reason values must not crash — default is operator_manual."""
        resp = await ready_client.post(
            "/control/safe-mode",
            json={"reason": "not_a_real_reason"},
        )
        assert resp.status == 200

    async def test_post_engage_malformed_body_uses_default_reason(self, ready_client):
        resp = await ready_client.post(
            "/control/safe-mode",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200

    async def test_delete_clear_200_when_ready(self, ready_client):
        resp = await ready_client.delete("/control/safe-mode")
        assert resp.status == 200
        body = await resp.json()
        assert body["status"] == "ok"
        assert "state" in body


# ── /metrics (OBS-003) ────────────────────────────────────────────────────────

class TestMetrics:
    async def test_200_response(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert resp.status == 200

    async def test_content_type_prometheus(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert "text/plain" in resp.content_type

    async def test_body_contains_help_lines(self, ready_client):
        text = await (await ready_client.get("/metrics")).text()
        assert "# HELP" in text

    async def test_body_contains_type_lines(self, ready_client):
        text = await (await ready_client.get("/metrics")).text()
        assert "# TYPE" in text

    async def test_metrics_available_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/metrics")
        assert resp.status == 200
