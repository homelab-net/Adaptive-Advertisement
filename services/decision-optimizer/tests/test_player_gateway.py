"""
Unit tests for PlayerGateway — path enforcement and outbound schema validation.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from decision_optimizer.player_gateway import PlayerGateway


# Shared fixture: gateway with schema loaded from actual contracts dir
@pytest.fixture
def gateway() -> PlayerGateway:
    return PlayerGateway()


# ---------------------------------------------------------------------------
# Outbound schema validation — _next_command
# ---------------------------------------------------------------------------

def test_valid_activate_creative_passes(gateway):
    raw = gateway._next_command(
        "activate_creative",
        {"manifest_id": "test-manifest", "min_dwell_ms": 5000},
    )
    msg = json.loads(raw)
    assert msg["command_type"] == "activate_creative"
    assert msg["schema_version"] == "1.0.0"
    assert "command_id" in msg
    assert msg["sequence_number"] == 1


def test_valid_freeze_passes(gateway):
    raw = gateway._next_command("freeze", {"reason": "cv_degraded"})
    msg = json.loads(raw)
    assert msg["command_type"] == "freeze"


def test_valid_safe_mode_passes(gateway):
    raw = gateway._next_command("safe_mode", {"reason": "supervisor_escalation"})
    msg = json.loads(raw)
    assert msg["command_type"] == "safe_mode"


def test_valid_clear_safe_mode_passes(gateway):
    raw = gateway._next_command("clear_safe_mode", None)
    msg = json.loads(raw)
    assert msg["command_type"] == "clear_safe_mode"


def test_invalid_command_type_raises(gateway):
    with pytest.raises(ValueError, match="invalid ICD-4 command"):
        gateway._next_command("nonexistent_command_type", None)


def test_invalid_command_rolls_back_sequence(gateway):
    assert gateway._sequence == 0
    with pytest.raises(ValueError):
        gateway._next_command("bad_type", None)
    # Sequence must not have advanced
    assert gateway._sequence == 0


def test_sequence_increments_on_valid_command(gateway):
    gateway._next_command("freeze", None)
    gateway._next_command("clear_safe_mode", None)
    assert gateway._sequence == 2


# ---------------------------------------------------------------------------
# _broadcast returns 0 on validation failure (no connections needed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_returns_zero_on_invalid_command(gateway):
    # No connections registered, but validation would fail first
    result = await gateway._broadcast("invalid_type", None)
    assert result == 0


@pytest.mark.asyncio
async def test_broadcast_returns_zero_when_no_connections(gateway):
    result = await gateway._broadcast("freeze", None)
    assert result == 0


# ---------------------------------------------------------------------------
# Path enforcement — _handler
# ---------------------------------------------------------------------------

def _make_ws(path=None, remote=("127.0.0.1", 9999)):
    ws = AsyncMock()
    ws.remote_address = remote
    # Simulate the .path attribute from websockets library
    ws.path = path
    ws.wait_closed = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_handler_accepts_correct_path(gateway):
    ws = _make_ws(path="/player/commands")
    await gateway._handler(ws)
    ws.close.assert_not_called()
    assert ws not in gateway._connections  # removed after wait_closed


@pytest.mark.asyncio
async def test_handler_rejects_wrong_path(gateway):
    ws = _make_ws(path="/wrong/path")
    await gateway._handler(ws)
    ws.close.assert_called_once()
    # Should not have been added to connections
    assert ws not in gateway._connections


@pytest.mark.asyncio
async def test_handler_accepts_no_path_attribute(gateway):
    """If path attribute is absent (older websockets version), accept."""
    ws = _make_ws(path=None)
    await gateway._handler(ws)
    ws.close.assert_not_called()
