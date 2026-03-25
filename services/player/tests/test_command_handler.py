"""
Unit tests for CommandHandler — ICD-4 command processing.

Coverage targets
----------------
- Valid commands are dispatched and produce transitions
- Schema violations are rejected
- Out-of-order sequence numbers are rejected
- Equal sequence numbers are rejected
- Duplicate command_ids are deduplicated (idempotency)
- Unknown manifest_id blocks activate_creative (no blank)
- All four command types route correctly
- reset_session() allows lower sequence numbers on reconnect
- Wrong schema_version is rejected (schema const constraint)
"""
import json
import pytest

from player.state import StateMachine, TransitionResult
from player.manifest_store import ManifestStore
from player.command_handler import CommandHandler
from tests.conftest import VALID_MANIFEST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cmd(
    seq: int,
    command_id: str,
    command_type: str,
    payload: dict | None = None,
    schema_version: str = "1.0.0",
) -> str:
    msg: dict = {
        "schema_version": schema_version,
        "command_id": command_id,
        "sequence_number": seq,
        "produced_at": "2026-01-01T00:00:00Z",
        "command_type": command_type,
    }
    if payload is not None:
        msg[command_type] = payload
    return json.dumps(msg)


def _activate(seq: int, cid: str, manifest_id: str = "manifest-1", dwell: int = 0) -> str:
    return _cmd(seq, cid, "activate_creative", {"manifest_id": manifest_id, "min_dwell_ms": dwell})


def _freeze(seq: int, cid: str, reason: str = "cv_degraded") -> str:
    return _cmd(seq, cid, "freeze", {"reason": reason})


def _safe_mode(seq: int, cid: str, reason: str = "operator_manual") -> str:
    return _cmd(seq, cid, "safe_mode", {"reason": reason})


def _clear_safe_mode(seq: int, cid: str) -> str:
    return _cmd(seq, cid, "clear_safe_mode")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store() -> ManifestStore:
    s = ManifestStore()
    s.put(VALID_MANIFEST)
    return s


@pytest.fixture()
def handler_with_transitions(store: ManifestStore):
    sm = StateMachine()
    transitions: list[TransitionResult] = []

    async def on_transition(result: TransitionResult) -> None:
        transitions.append(result)

    h = CommandHandler(sm, store, on_transition)
    # Expose transitions list on the handler instance for assertions
    h._test_transitions = transitions  # type: ignore[attr-defined]
    return h


# ---------------------------------------------------------------------------
# Happy-path dispatch
# ---------------------------------------------------------------------------

async def test_activate_creative_accepted(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(1, "c1"))
    assert len(handler_with_transitions._test_transitions) == 1
    assert handler_with_transitions._test_transitions[0].accepted


async def test_freeze_accepted(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(1, "c1"))
    await handler_with_transitions.handle_raw(_freeze(2, "c2"))
    assert len(handler_with_transitions._test_transitions) == 2


async def test_safe_mode_accepted(handler_with_transitions):
    await handler_with_transitions.handle_raw(_safe_mode(1, "c1"))
    t = handler_with_transitions._test_transitions
    assert len(t) == 1
    assert t[0].accepted


async def test_clear_safe_mode_accepted(handler_with_transitions):
    await handler_with_transitions.handle_raw(_safe_mode(1, "c1"))
    await handler_with_transitions.handle_raw(_clear_safe_mode(2, "c2"))
    assert len(handler_with_transitions._test_transitions) == 2


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

async def test_duplicate_command_id_deduplicated(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(1, "c1"))
    await handler_with_transitions.handle_raw(_activate(2, "c1"))  # same command_id
    # Second message has same command_id → deduplicated, no new transition
    assert len(handler_with_transitions._test_transitions) == 1


# ---------------------------------------------------------------------------
# Sequence ordering
# ---------------------------------------------------------------------------

async def test_out_of_order_sequence_rejected(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(5, "c1"))
    await handler_with_transitions.handle_raw(_activate(3, "c2"))  # seq 3 < 5
    assert len(handler_with_transitions._test_transitions) == 1


async def test_equal_sequence_rejected(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(5, "c1"))
    await handler_with_transitions.handle_raw(_activate(5, "c2"))  # seq 5 == 5
    assert len(handler_with_transitions._test_transitions) == 1


async def test_sequential_commands_all_accepted(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(1, "c1"))
    await handler_with_transitions.handle_raw(_freeze(2, "c2"))
    await handler_with_transitions.handle_raw(_safe_mode(3, "c3"))
    await handler_with_transitions.handle_raw(_clear_safe_mode(4, "c4"))
    assert len(handler_with_transitions._test_transitions) == 4


# ---------------------------------------------------------------------------
# Session reset
# ---------------------------------------------------------------------------

async def test_session_reset_allows_lower_sequence(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(10, "c1"))
    handler_with_transitions.reset_session()
    # After reset, seq=1 is valid again (1 > -1)
    await handler_with_transitions.handle_raw(_activate(1, "c2"))
    assert len(handler_with_transitions._test_transitions) == 2


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

async def test_invalid_json_rejected(handler_with_transitions):
    await handler_with_transitions.handle_raw("not valid json {{{")
    assert len(handler_with_transitions._test_transitions) == 0


async def test_missing_required_fields_rejected(handler_with_transitions):
    bad = json.dumps({"schema_version": "1.0.0"})  # missing command_id, seq, etc.
    await handler_with_transitions.handle_raw(bad)
    assert len(handler_with_transitions._test_transitions) == 0


async def test_wrong_schema_version_rejected(handler_with_transitions):
    # schema_version is a const "1.0.0" — any other value fails schema validation
    cmd = _cmd(1, "c1", "clear_safe_mode", schema_version="9.9.9")
    await handler_with_transitions.handle_raw(cmd)
    assert len(handler_with_transitions._test_transitions) == 0


async def test_invalid_command_type_rejected(handler_with_transitions):
    # command_type is an enum — unknown values fail schema validation
    cmd = json.dumps({
        "schema_version": "1.0.0",
        "command_id": "c1",
        "sequence_number": 1,
        "produced_at": "2026-01-01T00:00:00Z",
        "command_type": "does_not_exist",
    })
    await handler_with_transitions.handle_raw(cmd)
    assert len(handler_with_transitions._test_transitions) == 0


# ---------------------------------------------------------------------------
# Manifest enforcement
# ---------------------------------------------------------------------------

async def test_unknown_manifest_id_does_not_blank(handler_with_transitions):
    """An unknown manifest_id must produce a hold/fallback action, not a blank screen."""
    cmd = _activate(1, "c1", manifest_id="no-such-manifest")
    await handler_with_transitions.handle_raw(cmd)
    # A transition IS emitted (to keep screen safe), but it is not accepted
    assert len(handler_with_transitions._test_transitions) == 1
    assert not handler_with_transitions._test_transitions[0].accepted


async def test_known_manifest_activates(handler_with_transitions):
    await handler_with_transitions.handle_raw(_activate(1, "c1", manifest_id="manifest-1"))
    assert len(handler_with_transitions._test_transitions) == 1
    assert handler_with_transitions._test_transitions[0].accepted
