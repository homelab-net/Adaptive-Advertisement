"""
Health server endpoint tests for the decision-optimizer service.

Tests /healthz, /readyz, and /metrics (OBS-002, OBS-003).
Uses aiohttp's TestClient — no real MQTT broker or WebSocket server needed.
"""
import pytest
from unittest.mock import MagicMock

from decision_optimizer.health import make_health_app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mocks():
    loop = MagicMock()
    loop.status.return_value = {"last_manifest_id": None, "decision_count": 0}

    consumer = MagicMock()
    consumer.status.return_value = {"signals_received": 0, "last_signal_age_ms": None}

    gateway = MagicMock()
    gateway.status.return_value = {"connected_clients": 0}

    return loop, consumer, gateway


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def ready_client(aiohttp_client):
    loop, consumer, gateway = _make_mocks()
    is_ready = [True]
    app = await make_health_app(loop, consumer, gateway, is_ready)
    return await aiohttp_client(app)


@pytest.fixture
async def not_ready_client(aiohttp_client):
    loop, consumer, gateway = _make_mocks()
    is_ready = [False]
    app = await make_health_app(loop, consumer, gateway, is_ready)
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

    async def test_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/readyz")
        assert resp.status == 503

    async def test_readyz_includes_loop_status(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert "status" in body
        assert body["status"] == "ok"

    async def test_503_body_has_reason(self, not_ready_client):
        body = await (await not_ready_client.get("/readyz")).json()
        assert body["status"] == "not_ready"
        assert "reason" in body


# ── /metrics (OBS-003) ────────────────────────────────────────────────────────

class TestMetrics:
    async def test_200_response(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert resp.status == 200

    async def test_content_type_prometheus(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert "text/plain" in resp.content_type

    async def test_body_contains_help_lines(self, ready_client):
        resp = await ready_client.get("/metrics")
        text = await resp.text()
        assert "# HELP" in text

    async def test_body_contains_type_lines(self, ready_client):
        resp = await ready_client.get("/metrics")
        text = await resp.text()
        assert "# TYPE" in text

    async def test_metrics_available_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/metrics")
        assert resp.status == 200
