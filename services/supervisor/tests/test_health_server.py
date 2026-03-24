"""Tests for supervisor health HTTP endpoints."""
import pytest
from aiohttp.test_utils import TestClient, TestServer

from supervisor.service_table import ServiceState
from supervisor.health import make_health_app


@pytest.fixture
async def states() -> dict:
    return {
        "player": ServiceState(name="player"),
        "decision-optimizer": ServiceState(name="decision-optimizer"),
    }


@pytest.fixture
async def client(states):
    is_ready = [True]
    app = await make_health_app(states, is_ready)
    async with TestClient(TestServer(app)) as c:
        yield c, states


@pytest.mark.asyncio
async def test_healthz_200(client):
    c, _ = client
    resp = await c.get("/healthz")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_200_all_healthy(client):
    c, _ = client
    resp = await c.get("/readyz")
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ok"
    assert "degraded_services" not in data


@pytest.mark.asyncio
async def test_readyz_shows_degraded(client):
    c, states = client
    states["player"].is_healthy = False
    resp = await c.get("/readyz")
    assert resp.status == 200
    data = await resp.json()
    assert "player" in data["degraded_services"]


@pytest.mark.asyncio
async def test_readyz_503_not_ready(states):
    is_ready = [False]
    app = await make_health_app(states, is_ready)
    async with TestClient(TestServer(app)) as c:
        resp = await c.get("/readyz")
        assert resp.status == 503


@pytest.mark.asyncio
async def test_status_endpoint(client):
    c, states = client
    states["player"].restart_count = 2
    states["player"].in_boot_loop = False
    resp = await c.get("/status")
    assert resp.status == 200
    data = await resp.json()
    assert data["schema_version"] == "1.0.0"
    assert "player" in data["services"]
    assert data["services"]["player"]["restart_count"] == 2


@pytest.mark.asyncio
async def test_status_shows_boot_loop(client):
    c, states = client
    states["decision-optimizer"].in_boot_loop = True
    resp = await c.get("/status")
    data = await resp.json()
    assert data["services"]["decision-optimizer"]["in_boot_loop"] is True


# ── /metrics (OBS-003) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_200(client):
    c, _ = client
    resp = await c.get("/metrics")
    assert resp.status == 200


@pytest.mark.asyncio
async def test_metrics_content_type_prometheus(client):
    c, _ = client
    resp = await c.get("/metrics")
    assert "text/plain" in resp.content_type


@pytest.mark.asyncio
async def test_metrics_body_has_help_lines(client):
    c, _ = client
    resp = await c.get("/metrics")
    text = await resp.text()
    assert "# HELP" in text


@pytest.mark.asyncio
async def test_metrics_body_has_type_lines(client):
    c, _ = client
    resp = await c.get("/metrics")
    text = await resp.text()
    assert "# TYPE" in text
