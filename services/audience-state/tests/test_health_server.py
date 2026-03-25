"""
Health server endpoint tests for the audience-state service.

Tests /healthz, /readyz, and /metrics (OBS-002, OBS-003).
Uses aiohttp's TestClient — no real TCP server or MQTT broker needed.
"""
import pytest
from aiohttp.test_utils import TestClient, TestServer

from audience_state.health import make_health_app
from audience_state.observation_consumer import ObservationConsumer
from audience_state.signal_publisher import SignalPublisher
from audience_state.observation_store import ObservationWindow


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_components():
    window = ObservationWindow(window_ms=5000, min_stability_observations=3, confidence_freeze_threshold=0.5)
    consumer = ObservationConsumer(window)
    publisher = SignalPublisher()
    return consumer, publisher


@pytest.fixture
async def ready_client(aiohttp_client):
    consumer, publisher = _make_components()
    is_ready = [True]
    app = await make_health_app(consumer, publisher, is_ready)
    return await aiohttp_client(app)


@pytest.fixture
async def not_ready_client(aiohttp_client):
    consumer, publisher = _make_components()
    is_ready = [False]
    app = await make_health_app(consumer, publisher, is_ready)
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
        """Liveness is independent of readiness."""
        resp = await not_ready_client.get("/healthz")
        assert resp.status == 200

    async def test_content_type_json(self, ready_client):
        resp = await ready_client.get("/healthz")
        assert "application/json" in resp.content_type


# ── /readyz ───────────────────────────────────────────────────────────────────

class TestReadyz:
    async def test_200_when_ready(self, ready_client):
        resp = await ready_client.get("/readyz")
        assert resp.status == 200

    async def test_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/readyz")
        assert resp.status == 503

    async def test_readyz_body_status_ok(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert body["status"] == "ok"

    async def test_readyz_503_body_reason(self, not_ready_client):
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
        assert "# HELP" in text, "Response must contain Prometheus HELP lines"

    async def test_body_contains_type_lines(self, ready_client):
        resp = await ready_client.get("/metrics")
        text = await resp.text()
        assert "# TYPE" in text, "Response must contain Prometheus TYPE lines"

    async def test_metrics_available_when_not_ready(self, not_ready_client):
        """/metrics must be available even before service is fully ready."""
        resp = await not_ready_client.get("/metrics")
        assert resp.status == 200
