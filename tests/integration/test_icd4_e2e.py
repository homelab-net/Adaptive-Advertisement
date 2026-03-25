"""
Task 3 — ICD-4 end-to-end integration test.

Exercises the full WebSocket path:

  PlayerGateway (decision-optimizer WebSocket server)
      │  real TCP WebSocket connection
      ▼
  CommandHandler (player WebSocket client)
      │  dispatch
      ▼
  StateMachine + ManifestStore (player)
      │  TransitionResult
      ▼
  on_transition callback (captured for assertions)

All components run in-process using asyncio. No MQTT, no Docker, no hardware.
A free TCP port is allocated per test to prevent port conflicts.
"""
import asyncio
import json
import socket
import uuid
from datetime import datetime, timezone

import pytest

# ── player ────────────────────────────────────────────────────────────────────
from player.state import StateMachine, PlayerState
from player.manifest_store import ManifestStore
from player.command_handler import CommandHandler

# ── decision-optimizer ────────────────────────────────────────────────────────
from decision_optimizer.player_gateway import PlayerGateway
import decision_optimizer.config as do_config
import player.config as player_config


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _approved_manifest(manifest_id: str = "m-e2e-01") -> dict:
    return {
        "schema_version": "1.0.0",
        "manifest_id": manifest_id,
        "approved_at": "2026-01-01T00:00:00Z",
        "approved_by": "test-operator",
        "items": [
            {
                "item_id": "item-01",
                "asset_id": "test-asset.jpg",
                "asset_type": "image",
                "duration_ms": 5000,
            }
        ],
    }


async def _wait_for_player(gateway: PlayerGateway, timeout: float = 3.0) -> None:
    """Poll until at least one player is connected."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if gateway.player_count > 0:
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("player never connected to gateway within timeout")


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: wired gateway + command handler
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def icd4_stack():
    """
    Yields a dict with:
      gateway       — PlayerGateway (WebSocket server, started)
      handler       — CommandHandler (WebSocket client)
      state_machine — StateMachine
      manifest_store— ManifestStore (empty)
      transitions   — asyncio.Queue of TransitionResult objects
      handler_task  — asyncio.Task running CommandHandler.run()
      port          — TCP port in use
    """
    port = _free_port()

    # Patch module-level config so the gateway binds on our free port
    # and the handler connects to the same address.
    orig_host = do_config.PLAYER_WS_HOST
    orig_port = do_config.PLAYER_WS_PORT
    orig_path = do_config.PLAYER_WS_PATH
    orig_url = player_config.DECISION_OPTIMIZER_WS_URL

    do_config.PLAYER_WS_HOST = "127.0.0.1"
    do_config.PLAYER_WS_PORT = port
    do_config.PLAYER_WS_PATH = "/player/commands"
    player_config.DECISION_OPTIMIZER_WS_URL = (
        f"ws://127.0.0.1:{port}/player/commands"
    )

    gateway = PlayerGateway()
    await gateway.start()

    state_machine = StateMachine()
    manifest_store = ManifestStore()

    transitions: asyncio.Queue = asyncio.Queue()

    async def on_transition(result):
        await transitions.put(result)

    handler = CommandHandler(state_machine, manifest_store, on_transition)
    handler_task = asyncio.create_task(handler.run())

    # Wait for the player to connect before yielding
    await _wait_for_player(gateway)

    yield {
        "gateway": gateway,
        "handler": handler,
        "state_machine": state_machine,
        "manifest_store": manifest_store,
        "transitions": transitions,
        "handler_task": handler_task,
        "port": port,
    }

    # Teardown
    handler_task.cancel()
    await asyncio.gather(handler_task, return_exceptions=True)
    await gateway.stop()

    # Restore config
    do_config.PLAYER_WS_HOST = orig_host
    do_config.PLAYER_WS_PORT = orig_port
    do_config.PLAYER_WS_PATH = orig_path
    player_config.DECISION_OPTIMIZER_WS_URL = orig_url


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

async def test_player_connects_to_gateway(icd4_stack):
    """Gateway sees exactly one connected player after fixture setup."""
    assert icd4_stack["gateway"].player_count == 1


async def test_freeze_command_delivered_end_to_end(icd4_stack):
    """
    Gateway broadcasts freeze → CommandHandler receives it → StateMachine freezes.
    Player starts in FALLBACK; freeze keeps it in FALLBACK (hold action).
    """
    gateway = icd4_stack["gateway"]
    transitions = icd4_stack["transitions"]
    sm = icd4_stack["state_machine"]

    sent = await gateway.send_freeze(reason="cv_degraded")
    assert sent == 1

    result = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert result is not None
    # FALLBACK + freeze → hold (never-blank invariant)
    assert sm.state == PlayerState.FALLBACK


async def test_activate_creative_delivers_to_state_machine(icd4_stack):
    """
    Gateway broadcasts activate_creative with an approved manifest →
    CommandHandler validates and dispatches → StateMachine transitions to ACTIVE.
    """
    gateway = icd4_stack["gateway"]
    manifest_store = icd4_stack["manifest_store"]
    transitions = icd4_stack["transitions"]
    sm = icd4_stack["state_machine"]

    # Load an approved manifest into the player's store
    manifest = _approved_manifest("m-e2e-01")
    err = manifest_store.put(manifest)
    assert err is None

    sent = await gateway.send_activate_creative(
        "m-e2e-01", min_dwell_ms=1000, rationale="e2e test"
    )
    assert sent == 1

    result = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert result.accepted is True
    assert result.manifest_id == "m-e2e-01"
    assert sm.state == PlayerState.ACTIVE


async def test_unknown_manifest_rejected_never_blank(icd4_stack):
    """
    activate_creative for an unknown manifest_id is rejected by CommandHandler.
    State machine stays in FALLBACK — never-blank invariant preserved.
    """
    gateway = icd4_stack["gateway"]
    transitions = icd4_stack["transitions"]
    sm = icd4_stack["state_machine"]

    # Do NOT load any manifest — store is empty
    sent = await gateway.send_activate_creative(
        "m-does-not-exist", min_dwell_ms=1000
    )
    assert sent == 1

    result = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert result.accepted is False
    assert result.reason == "unknown_manifest"
    # Still in FALLBACK — never blanked
    assert sm.state == PlayerState.FALLBACK


async def test_safe_mode_command_delivered(icd4_stack):
    """Gateway broadcasts safe_mode → StateMachine enters SAFE_MODE."""
    gateway = icd4_stack["gateway"]
    transitions = icd4_stack["transitions"]
    sm = icd4_stack["state_machine"]

    sent = await gateway.send_safe_mode(reason="supervisor_escalation")
    assert sent == 1

    result = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert sm.state == PlayerState.SAFE_MODE


async def test_sequence_ordering_enforced(icd4_stack):
    """
    A command with a sequence number ≤ the last applied is rejected.
    We send two freeze commands; only the first must produce a transition.
    The second is sent by directly calling handle_raw with a stale seq.
    """
    gateway = icd4_stack["gateway"]
    handler = icd4_stack["handler"]
    transitions = icd4_stack["transitions"]

    # Send via gateway — gets seq=N
    await gateway.send_freeze()
    await asyncio.wait_for(transitions.get(), timeout=2.0)

    # Craft a raw message with seq=1 (stale — gateway is now at seq≥1)
    stale_msg = json.dumps({
        "schema_version": "1.0.0",
        "command_id": str(uuid.uuid4()),
        "sequence_number": 1,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "command_type": "freeze",
    })
    await handler.handle_raw(stale_msg)

    # Queue should be empty — stale command was silently dropped
    assert transitions.empty()


async def test_duplicate_command_id_ignored(icd4_stack):
    """
    A command_id that has already been applied is silently deduplicated.
    """
    gateway = icd4_stack["gateway"]
    handler = icd4_stack["handler"]
    transitions = icd4_stack["transitions"]

    # First freeze via gateway — captures a real command_id from the seq
    await gateway.send_freeze()
    first = await asyncio.wait_for(transitions.get(), timeout=2.0)

    # Replay the exact same message (same command_id, but seq is now stale too)
    # Use handle_raw directly to inject a replay with a novel high seq but known command_id
    replay_msg = json.dumps({
        "schema_version": "1.0.0",
        "command_id": str(uuid.uuid4()),   # fresh id — but let's test with explicit duplicate
        "sequence_number": 9999,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "command_type": "freeze",
    })
    # Inject once — accepted
    await handler.handle_raw(replay_msg)
    await asyncio.wait_for(transitions.get(), timeout=2.0)

    # Inject same message again — duplicate command_id → dropped
    await handler.handle_raw(replay_msg)
    await asyncio.sleep(0.1)
    assert transitions.empty()


async def test_session_reset_accepts_lower_sequence(icd4_stack):
    """
    After reset_session(), sequence tracking restarts at -1 so the next
    command (even seq=1) is accepted regardless of prior session state.
    """
    gateway = icd4_stack["gateway"]
    handler = icd4_stack["handler"]
    transitions = icd4_stack["transitions"]

    # Advance the session sequence
    await gateway.send_freeze()
    await asyncio.wait_for(transitions.get(), timeout=2.0)

    # Reset session (simulates reconnect)
    handler.reset_session()

    # Now inject a low seq number directly — should be accepted
    low_seq_msg = json.dumps({
        "schema_version": "1.0.0",
        "command_id": str(uuid.uuid4()),
        "sequence_number": 1,
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "command_type": "freeze",
    })
    await handler.handle_raw(low_seq_msg)
    result = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert result is not None


async def test_multiple_manifests_sequential_activation(icd4_stack):
    """
    Activate manifest A, then manifest B. Both transitions succeed;
    state machine ends on ACTIVE with manifest B.
    """
    gateway = icd4_stack["gateway"]
    manifest_store = icd4_stack["manifest_store"]
    transitions = icd4_stack["transitions"]
    sm = icd4_stack["state_machine"]

    manifest_store.put(_approved_manifest("m-alpha"))
    manifest_store.put(_approved_manifest("m-beta"))

    await gateway.send_activate_creative("m-alpha", min_dwell_ms=100)
    r1 = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert r1.accepted
    assert sm.state == PlayerState.ACTIVE

    await asyncio.sleep(0.15)  # allow min_dwell_ms=100 to elapse
    await gateway.send_activate_creative("m-beta", min_dwell_ms=100)
    r2 = await asyncio.wait_for(transitions.get(), timeout=2.0)
    assert r2.accepted
    assert r2.manifest_id == "m-beta"
    assert sm.state == PlayerState.ACTIVE
