"""
Unit tests for DecisionLoop — 1 Hz policy evaluation and command dispatch.

The PlayerGateway is replaced by a MockGateway that records sent commands.
The SignalConsumer is used directly — we inject signals via consumer.process().
"""
import json
import pytest
from typing import Optional
from unittest.mock import AsyncMock

from decision_optimizer.policy import Rule, PolicyConfig, PolicyEngine
from decision_optimizer.signal_consumer import SignalConsumer
from decision_optimizer.decision_loop import DecisionLoop
from tests.conftest import make_signal


# ---------------------------------------------------------------------------
# Mock gateway
# ---------------------------------------------------------------------------

class MockGateway:
    """Records all commands sent by the decision loop."""

    def __init__(self, player_count: int = 1) -> None:
        self._player_count = player_count
        self.sent: list[dict] = []

    @property
    def player_count(self) -> int:
        return self._player_count

    async def send_activate_creative(
        self,
        manifest_id: str,
        min_dwell_ms: int,
        cooldown_ms: int = 0,
        rationale: Optional[str] = None,
    ) -> int:
        self.sent.append({
            "type": "activate_creative",
            "manifest_id": manifest_id,
            "min_dwell_ms": min_dwell_ms,
            "cooldown_ms": cooldown_ms,
        })
        return self._player_count

    async def send_freeze(self, reason: Optional[str] = None) -> int:
        self.sent.append({"type": "freeze", "reason": reason})
        return self._player_count

    async def send_safe_mode(self, reason: Optional[str] = None) -> int:
        self.sent.append({"type": "safe_mode", "reason": reason})
        return self._player_count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_engine(rules=None) -> PolicyEngine:
    if rules is None:
        rules = [
            Rule("group",   priority=20, manifest_id="m-group",   presence_count_gte=3),
            Rule("single",  priority=10, manifest_id="m-single",  presence_count_gte=1),
            Rule("attract", priority=0,  manifest_id="m-attract"),
        ]
    return PolicyEngine(PolicyConfig(
        rules=rules, min_dwell_ms=5000, cooldown_ms=2000
    ))


@pytest.fixture()
def consumer() -> SignalConsumer:
    return SignalConsumer()


@pytest.fixture()
def gateway() -> MockGateway:
    return MockGateway()


@pytest.fixture()
def loop(consumer, gateway) -> DecisionLoop:
    return DecisionLoop(policy=_make_engine(), consumer=consumer, gateway=gateway)


def inject(consumer: SignalConsumer, **kwargs) -> None:
    """Helper: inject a signal into the consumer with a unique auto message_id."""
    _counter = getattr(inject, "_counter", 0) + 1
    setattr(inject, "_counter", _counter)
    kwargs.setdefault("message_id", f"auto-{_counter}")
    sig = make_signal(**kwargs)
    consumer.process(json.dumps(sig).encode())


# ---------------------------------------------------------------------------
# Basic dispatch
# ---------------------------------------------------------------------------

async def test_no_signal_no_command(loop, gateway):
    await loop._tick()
    assert gateway.sent == []


async def test_first_signal_triggers_activate(loop, consumer, gateway):
    inject(consumer, count=1, confidence=0.9)
    await loop._tick()
    assert len(gateway.sent) == 1
    assert gateway.sent[0]["type"] == "activate_creative"
    assert gateway.sent[0]["manifest_id"] == "m-single"


async def test_same_manifest_no_repeat_command(loop, consumer, gateway):
    inject(consumer, count=1, confidence=0.9)
    await loop._tick()  # sends activate m-single
    inject(consumer, count=1, confidence=0.9, message_id="msg-2")
    await loop._tick()  # manifest unchanged — no command
    assert len(gateway.sent) == 1


async def test_manifest_change_sends_new_command(loop, consumer, gateway):
    inject(consumer, count=1, confidence=0.9)
    await loop._tick()  # → m-single
    inject(consumer, count=5, confidence=0.9, message_id="msg-2")
    await loop._tick()  # → m-group
    assert len(gateway.sent) == 2
    assert gateway.sent[1]["manifest_id"] == "m-group"


async def test_zero_count_selects_attract(loop, consumer, gateway):
    inject(consumer, count=0, confidence=0.9)
    await loop._tick()
    assert gateway.sent[0]["manifest_id"] == "m-attract"


async def test_command_carries_dwell_and_cooldown(loop, consumer, gateway):
    inject(consumer, count=1, confidence=0.9)
    await loop._tick()
    cmd = gateway.sent[0]
    assert cmd["min_dwell_ms"] == 5000
    assert cmd["cooldown_ms"] == 2000


# ---------------------------------------------------------------------------
# Freeze conditions
# ---------------------------------------------------------------------------

async def test_pipeline_degraded_sends_freeze(loop, consumer, gateway):
    inject(consumer, count=1, pipeline_degraded=True)
    await loop._tick()
    assert gateway.sent[0]["type"] == "freeze"
    assert gateway.sent[0]["reason"] == "cv_degraded"


async def test_freeze_decision_flag_sends_freeze(loop, consumer, gateway):
    inject(consumer, count=1, freeze_decision=True)
    await loop._tick()
    assert gateway.sent[0]["type"] == "freeze"


async def test_freeze_not_repeated_on_consecutive_ticks(loop, consumer, gateway):
    inject(consumer, count=1, pipeline_degraded=True)
    await loop._tick()  # first freeze
    inject(consumer, count=1, pipeline_degraded=True, message_id="msg-2")
    await loop._tick()  # still degraded — don't re-send freeze
    assert len(gateway.sent) == 1


async def test_stale_signal_sends_freeze(loop, consumer, gateway):
    """Simulate a stale signal by monkey-patching the age reporter."""
    inject(consumer, count=1)
    # Monkey-patch signal_age_ms to return a large value
    consumer.signal_age_ms = lambda: 99_999
    await loop._tick()
    assert gateway.sent[0]["type"] == "freeze"
    assert gateway.sent[0]["reason"] == "decision_degraded"


# ---------------------------------------------------------------------------
# Unfreeze (lifting a freeze)
# ---------------------------------------------------------------------------

async def test_recovery_after_freeze_sends_activate(loop, consumer, gateway):
    inject(consumer, count=1, pipeline_degraded=True)
    await loop._tick()  # freeze
    assert loop._player_frozen is True

    inject(consumer, count=1, pipeline_degraded=False, message_id="msg-2")
    await loop._tick()  # recovered — send activate
    assert len(gateway.sent) == 2
    assert gateway.sent[1]["type"] == "activate_creative"
    assert loop._player_frozen is False


async def test_unfreeze_sends_activate_even_if_manifest_unchanged(loop, consumer, gateway):
    """After freeze, activate_creative must be sent to lift the player's freeze."""
    inject(consumer, count=1)
    await loop._tick()  # → m-single (first time)
    inject(consumer, count=1, pipeline_degraded=True, message_id="msg-2")
    await loop._tick()  # freeze
    inject(consumer, count=1, pipeline_degraded=False, message_id="msg-3")
    await loop._tick()  # same manifest, but was frozen → must send activate
    assert len(gateway.sent) == 3
    assert gateway.sent[2]["type"] == "activate_creative"
    assert gateway.sent[2]["manifest_id"] == "m-single"


# ---------------------------------------------------------------------------
# No connected players
# ---------------------------------------------------------------------------

async def test_commands_sent_with_no_players_are_counted(consumer, gateway):
    gw = MockGateway(player_count=0)
    dl = DecisionLoop(policy=_make_engine(), consumer=consumer, gateway=gw)
    inject(consumer, count=1, confidence=0.9)
    await dl._tick()
    # Command IS attempted (decision loop doesn't gate on player count)
    assert len(gw.sent) == 1


# ---------------------------------------------------------------------------
# Status observability
# ---------------------------------------------------------------------------

async def test_status_reflects_current_state(loop, consumer, gateway):
    inject(consumer, count=1, confidence=0.9)
    await loop._tick()
    s = loop.status()
    assert s["current_manifest_id"] == "m-single"
    assert s["player_frozen"] is False
    assert s["tick_count"] == 1
    assert s["command_count"] == 1
