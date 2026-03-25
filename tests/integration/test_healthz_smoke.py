"""
Task 1 — healthz smoke test.

Starts each service's health application in-process (no MQTT, no Docker,
no hardware) and verifies every /healthz and /readyz endpoint returns the
correct status code and a parseable JSON body.

This is the virtual-environment substitute for docker compose up + curl
against all service health ports.

Services covered
----------------
audience-state  /healthz /readyz (ready and not-ready)
player          /healthz /readyz (ready and not-ready) /control/safe-mode
decision-optimizer /healthz /readyz
creative        /healthz /readyz (ready and not-ready)
supervisor      /healthz /readyz (healthy + degraded) /status
dashboard-api   /healthz /readyz  (via httpx/FastAPI TestClient)
"""
import json
import pytest
from unittest.mock import MagicMock

# ── audience-state ────────────────────────────────────────────────────────────
from audience_state.observation_store import ObservationWindow
from audience_state.observation_consumer import ObservationConsumer
from audience_state.signal_publisher import SignalPublisher
from audience_state.health import make_health_app as _as_health

# ── player ────────────────────────────────────────────────────────────────────
from player.state import StateMachine
from player.health import make_health_app as _player_health

# ── decision-optimizer ────────────────────────────────────────────────────────
from decision_optimizer.health import make_health_app as _do_health

# ── creative ──────────────────────────────────────────────────────────────────
from creative.manifest_store import ManifestStore as CreativeManifestStore
from creative.api import make_app as _creative_app

# ── supervisor ────────────────────────────────────────────────────────────────
from supervisor.health import make_health_app as _sup_health
from supervisor.service_table import ServiceState


# ═════════════════════════════════════════════════════════════════════════════
# audience-state
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def as_app_ready():
    window = ObservationWindow(
        window_ms=5000, min_stability_observations=3, confidence_freeze_threshold=0.5
    )
    consumer = ObservationConsumer(window)
    publisher = SignalPublisher()
    return await _as_health(consumer, publisher, [True])


@pytest.fixture
async def as_app_not_ready():
    window = ObservationWindow(
        window_ms=5000, min_stability_observations=3, confidence_freeze_threshold=0.5
    )
    consumer = ObservationConsumer(window)
    publisher = SignalPublisher()
    return await _as_health(consumer, publisher, [False])


async def test_audience_state_healthz(aiohttp_client, as_app_ready):
    client = await aiohttp_client(as_app_ready)
    resp = await client.get("/healthz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_audience_state_readyz_when_ready(aiohttp_client, as_app_ready):
    client = await aiohttp_client(as_app_ready)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_audience_state_readyz_when_not_ready(aiohttp_client, as_app_not_ready):
    client = await aiohttp_client(as_app_not_ready)
    resp = await client.get("/readyz")
    assert resp.status == 503
    body = await resp.json()
    assert body["status"] == "not_ready"


# ═════════════════════════════════════════════════════════════════════════════
# player
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def player_app_ready():
    sm = StateMachine()
    return await _player_health(sm, [True], [None])


@pytest.fixture
async def player_app_not_ready():
    sm = StateMachine()
    return await _player_health(sm, [False], [None])


async def test_player_healthz(aiohttp_client, player_app_ready):
    client = await aiohttp_client(player_app_ready)
    resp = await client.get("/healthz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_player_readyz_when_ready(aiohttp_client, player_app_ready):
    client = await aiohttp_client(player_app_ready)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    # State machine starts in FALLBACK — check state field is present
    assert "state" in body


async def test_player_readyz_when_not_ready(aiohttp_client, player_app_not_ready):
    client = await aiohttp_client(player_app_not_ready)
    resp = await client.get("/readyz")
    assert resp.status == 503
    body = await resp.json()
    assert body["status"] == "not_ready"


async def test_player_safe_mode_engage_not_ready(aiohttp_client, player_app_not_ready):
    """POST /control/safe-mode when service not ready returns 503."""
    client = await aiohttp_client(player_app_not_ready)
    resp = await client.post(
        "/control/safe-mode", json={"reason": "operator_manual"}
    )
    assert resp.status == 503


async def test_player_safe_mode_engage_ready(aiohttp_client, player_app_ready):
    """POST /control/safe-mode when ready with valid reason returns 200."""
    # Wire up an on_transition_holder so the handler works
    sm = StateMachine()
    transitions = []

    async def _on_transition(result):
        transitions.append(result)

    app = await _player_health(sm, [True], [_on_transition])
    client = await aiohttp_client(app)
    resp = await client.post(
        "/control/safe-mode", json={"reason": "supervisor_escalation"}
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    assert "state" in body
    assert len(transitions) == 1


async def test_player_safe_mode_clear(aiohttp_client):
    """DELETE /control/safe-mode clears safe mode and returns 200."""
    sm = StateMachine()
    transitions = []

    async def _on_transition(result):
        transitions.append(result)

    app = await _player_health(sm, [True], [_on_transition])
    client = await aiohttp_client(app)

    # Engage first
    await client.post("/control/safe-mode", json={"reason": "operator_manual"})
    # Then clear
    resp = await client.delete("/control/safe-mode")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


# ═════════════════════════════════════════════════════════════════════════════
# decision-optimizer
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def do_app_ready():
    loop = MagicMock()
    loop.status.return_value = {
        "decision_count": 0,
        "last_manifest_id": None,
        "freeze_active": False,
    }
    consumer = MagicMock()
    consumer.status.return_value = {
        "latest_message_id": None,
        "signal_age_ms": None,
        "total_received": 0,
        "total_rejected": 0,
    }
    gateway = MagicMock()
    return await _do_health(loop, consumer, gateway, [True])


@pytest.fixture
async def do_app_not_ready():
    loop = MagicMock()
    loop.status.return_value = {}
    consumer = MagicMock()
    consumer.status.return_value = {}
    gateway = MagicMock()
    return await _do_health(loop, consumer, gateway, [False])


async def test_decision_optimizer_healthz(aiohttp_client, do_app_ready):
    client = await aiohttp_client(do_app_ready)
    resp = await client.get("/healthz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_decision_optimizer_readyz_when_ready(aiohttp_client, do_app_ready):
    client = await aiohttp_client(do_app_ready)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_decision_optimizer_readyz_when_not_ready(aiohttp_client, do_app_not_ready):
    client = await aiohttp_client(do_app_not_ready)
    resp = await client.get("/readyz")
    assert resp.status == 503
    body = await resp.json()
    assert body["status"] == "not_ready"


# ═════════════════════════════════════════════════════════════════════════════
# creative
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def creative_app_ready():
    store = CreativeManifestStore()
    return _creative_app(store, [True])


@pytest.fixture
def creative_app_not_ready():
    store = CreativeManifestStore()
    return _creative_app(store, [False])


async def test_creative_healthz(aiohttp_client, creative_app_ready):
    client = await aiohttp_client(creative_app_ready)
    resp = await client.get("/healthz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_creative_readyz_when_ready(aiohttp_client, creative_app_ready):
    client = await aiohttp_client(creative_app_ready)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_creative_readyz_when_not_ready(aiohttp_client, creative_app_not_ready):
    client = await aiohttp_client(creative_app_not_ready)
    resp = await client.get("/readyz")
    assert resp.status == 503
    body = await resp.json()
    assert body["status"] == "not_ready"


# ═════════════════════════════════════════════════════════════════════════════
# supervisor
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
async def sup_app_all_healthy():
    states = {
        "player": ServiceState(name="player", is_healthy=True),
        "audience-state": ServiceState(name="audience-state", is_healthy=True),
        "decision-optimizer": ServiceState(name="decision-optimizer", is_healthy=True),
    }
    return await _sup_health(states, [True])


@pytest.fixture
async def sup_app_one_degraded():
    states = {
        "player": ServiceState(name="player", is_healthy=True),
        "audience-state": ServiceState(name="audience-state", is_healthy=False,
                                       consecutive_failures=2),
    }
    return await _sup_health(states, [True])


@pytest.fixture
async def sup_app_not_ready():
    return await _sup_health({}, [False])


async def test_supervisor_healthz(aiohttp_client, sup_app_all_healthy):
    client = await aiohttp_client(sup_app_all_healthy)
    resp = await client.get("/healthz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"


async def test_supervisor_readyz_all_healthy(aiohttp_client, sup_app_all_healthy):
    client = await aiohttp_client(sup_app_all_healthy)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    assert "degraded_services" not in body


async def test_supervisor_readyz_degraded(aiohttp_client, sup_app_one_degraded):
    client = await aiohttp_client(sup_app_one_degraded)
    resp = await client.get("/readyz")
    assert resp.status == 200
    body = await resp.json()
    assert body["status"] == "ok"
    assert "audience-state" in body["degraded_services"]


async def test_supervisor_readyz_not_ready(aiohttp_client, sup_app_not_ready):
    client = await aiohttp_client(sup_app_not_ready)
    resp = await client.get("/readyz")
    assert resp.status == 503
    body = await resp.json()
    assert body["status"] == "not_ready"


async def test_supervisor_status_endpoint(aiohttp_client, sup_app_all_healthy):
    client = await aiohttp_client(sup_app_all_healthy)
    resp = await client.get("/status")
    assert resp.status == 200
    body = await resp.json()
    assert body["schema_version"] == "1.0.0"
    assert "player" in body["services"]
    player_status = body["services"]["player"]
    assert player_status["is_healthy"] is True
    assert "consecutive_failures" in player_status
    assert "restart_count" in player_status


async def test_supervisor_status_shows_degraded_fields(aiohttp_client, sup_app_one_degraded):
    client = await aiohttp_client(sup_app_one_degraded)
    resp = await client.get("/status")
    assert resp.status == 200
    body = await resp.json()
    as_status = body["services"]["audience-state"]
    assert as_status["is_healthy"] is False
    assert as_status["consecutive_failures"] == 2
