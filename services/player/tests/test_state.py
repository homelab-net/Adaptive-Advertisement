"""
Unit tests for the player state machine.

Coverage targets
----------------
- Every state's response to every command type
- Never-blank invariant: every transition must produce a display action
- Dwell enforcement
- Cooldown enforcement
- Connection-loss behaviour per state
"""
import pytest

from player.state import StateMachine, PlayerState, TransitionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def activate(sm: StateMachine, manifest_id: str = "m1", dwell: int = 0, cooldown: int = 0) -> TransitionResult:
    return sm.on_activate_creative(manifest_id, min_dwell_ms=dwell, cooldown_ms=cooldown)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_starts_in_fallback(self):
        sm = StateMachine()
        assert sm.state == PlayerState.FALLBACK

    def test_no_active_manifest_at_start(self):
        sm = StateMachine()
        assert sm.active_manifest_id is None

    def test_status_returns_dict(self):
        sm = StateMachine()
        s = sm.status()
        assert s["state"] == "fallback"
        assert s["active_manifest_id"] is None


# ---------------------------------------------------------------------------
# activate_creative
# ---------------------------------------------------------------------------

class TestActivateCreative:
    def test_fallback_to_active(self):
        sm = StateMachine()
        r = activate(sm, "m1")
        assert r.accepted
        assert r.new_state == PlayerState.ACTIVE
        assert r.action == "play_manifest"
        assert r.manifest_id == "m1"
        assert sm.state == PlayerState.ACTIVE
        assert sm.active_manifest_id == "m1"

    def test_active_to_active_after_zero_dwell(self):
        sm = StateMachine()
        activate(sm, "m1", dwell=0)
        r = activate(sm, "m2", dwell=0)
        assert r.accepted
        assert sm.active_manifest_id == "m2"

    def test_blocked_by_dwell(self):
        sm = StateMachine()
        activate(sm, "m1", dwell=60_000)
        r = activate(sm, "m2", dwell=0)
        assert not r.accepted
        assert r.reason == "dwell_not_elapsed"
        assert sm.active_manifest_id == "m1"

    def test_blocked_in_safe_mode(self):
        sm = StateMachine()
        activate(sm, "m1")
        sm.on_safe_mode("operator_manual")
        r = activate(sm, "m2")
        assert not r.accepted
        assert r.reason == "safe_mode"
        assert sm.state == PlayerState.SAFE_MODE

    def test_accepted_in_frozen_lifts_freeze(self):
        """activate_creative in FROZEN state must be accepted (CRM-002 decision)."""
        sm = StateMachine()
        activate(sm, "m1")
        sm.on_freeze("cv_degraded")
        assert sm.state == PlayerState.FROZEN
        r = activate(sm, "m2")
        assert r.accepted
        assert sm.state == PlayerState.ACTIVE
        assert sm.active_manifest_id == "m2"

    def test_cooldown_blocks_reactivation(self):
        sm = StateMachine()
        # Activate m1 (no cooldown on m1 itself)
        activate(sm, "m1", dwell=0, cooldown=0)
        # Activate m2 with cooldown_ms=60_000 — means m2 cannot be reactivated for 60s
        activate(sm, "m2", dwell=0, cooldown=60_000)
        # Switch to m3 — this deactivates m2, recording its 60s cooldown
        activate(sm, "m3", dwell=0, cooldown=0)
        # Try to reactivate m2 — should be in cooldown
        r = activate(sm, "m2", dwell=0)
        assert not r.accepted
        assert r.reason == "cooldown"

    def test_zero_cooldown_allows_immediate_reactivation(self):
        sm = StateMachine()
        activate(sm, "m1", dwell=0, cooldown=0)
        activate(sm, "m2", dwell=0, cooldown=0)
        r = activate(sm, "m1", dwell=0)
        assert r.accepted


# ---------------------------------------------------------------------------
# freeze
# ---------------------------------------------------------------------------

class TestFreeze:
    def test_active_to_frozen(self):
        sm = StateMachine()
        activate(sm)
        r = sm.on_freeze("cv_degraded")
        assert r.accepted
        assert sm.state == PlayerState.FROZEN
        assert r.action == "hold"
        assert r.manifest_id == "m1"

    def test_freeze_in_fallback_stays_fallback(self):
        sm = StateMachine()
        r = sm.on_freeze("cv_degraded")
        assert not r.accepted
        assert sm.state == PlayerState.FALLBACK
        assert r.action == "show_fallback"

    def test_freeze_in_safe_mode_is_ignored(self):
        sm = StateMachine()
        sm.on_safe_mode("operator_manual")
        r = sm.on_freeze("cv_degraded")
        assert not r.accepted
        assert sm.state == PlayerState.SAFE_MODE
        assert r.action == "show_fallback"

    def test_freeze_while_already_frozen_updates_reason(self):
        sm = StateMachine()
        activate(sm)
        sm.on_freeze("cv_degraded")
        r = sm.on_freeze("thermal_protection")
        assert r.accepted
        assert sm.state == PlayerState.FROZEN
        assert sm._freeze_reason == "thermal_protection"


# ---------------------------------------------------------------------------
# safe_mode
# ---------------------------------------------------------------------------

class TestSafeMode:
    def test_active_to_safe_mode(self):
        sm = StateMachine()
        activate(sm)
        r = sm.on_safe_mode("operator_manual")
        assert r.accepted
        assert sm.state == PlayerState.SAFE_MODE
        assert r.action == "show_fallback"
        assert sm.active_manifest_id is None

    def test_fallback_to_safe_mode(self):
        sm = StateMachine()
        r = sm.on_safe_mode("boot_loop_protection")
        assert r.accepted
        assert sm.state == PlayerState.SAFE_MODE

    def test_frozen_to_safe_mode(self):
        sm = StateMachine()
        activate(sm)
        sm.on_freeze("cv_degraded")
        r = sm.on_safe_mode("supervisor_escalation")
        assert r.accepted
        assert sm.state == PlayerState.SAFE_MODE

    def test_clear_safe_mode_returns_to_fallback(self):
        sm = StateMachine()
        sm.on_safe_mode("operator_manual")
        r = sm.on_clear_safe_mode()
        assert r.accepted
        assert sm.state == PlayerState.FALLBACK
        assert r.action == "show_fallback"

    def test_clear_safe_mode_noop_when_not_in_safe_mode(self):
        sm = StateMachine()
        r = sm.on_clear_safe_mode()
        assert not r.accepted
        assert sm.state == PlayerState.FALLBACK

    def test_clear_safe_mode_clears_reason(self):
        sm = StateMachine()
        sm.on_safe_mode("operator_manual")
        sm.on_clear_safe_mode()
        assert sm._safe_mode_reason is None


# ---------------------------------------------------------------------------
# connection_lost
# ---------------------------------------------------------------------------

class TestConnectionLost:
    def test_active_to_fallback(self):
        sm = StateMachine()
        activate(sm)
        r = sm.on_connection_lost()
        assert r.accepted
        assert sm.state == PlayerState.FALLBACK
        assert r.action == "show_fallback"

    def test_frozen_to_fallback(self):
        sm = StateMachine()
        activate(sm)
        sm.on_freeze("cv_degraded")
        r = sm.on_connection_lost()
        assert r.accepted
        assert sm.state == PlayerState.FALLBACK

    def test_fallback_stays_fallback(self):
        sm = StateMachine()
        r = sm.on_connection_lost()
        assert sm.state == PlayerState.FALLBACK
        assert r.action == "show_fallback"

    def test_safe_mode_survives_connection_loss(self):
        """SAFE_MODE is sticky — connection loss must not clear it."""
        sm = StateMachine()
        sm.on_safe_mode("operator_manual")
        r = sm.on_connection_lost()
        assert sm.state == PlayerState.SAFE_MODE
        assert r.action == "show_fallback"


# ---------------------------------------------------------------------------
# Never-blank invariant
# ---------------------------------------------------------------------------

class TestNeverBlankInvariant:
    """
    Every transition must produce one of the three safe display actions.
    'hold' continues current content; 'show_fallback' and 'play_manifest' are
    explicit display commands. None result in a blank screen.
    """
    VALID_ACTIONS = {"play_manifest", "show_fallback", "hold"}

    def _all_transitions(self) -> list[TransitionResult]:
        sm = StateMachine()
        results = []
        results.append(activate(sm, "m1"))             # FALLBACK → ACTIVE
        results.append(sm.on_freeze("cv_degraded"))    # ACTIVE → FROZEN
        results.append(activate(sm, "m2"))             # FROZEN → ACTIVE (CRM-002)
        results.append(sm.on_safe_mode("operator_manual"))    # ACTIVE → SAFE_MODE
        results.append(sm.on_clear_safe_mode())        # SAFE_MODE → FALLBACK
        results.append(activate(sm, "m3"))             # FALLBACK → ACTIVE
        results.append(sm.on_connection_lost())        # ACTIVE → FALLBACK
        # Rejected transitions also need safe actions
        sm2 = StateMachine()
        results.append(sm2.on_clear_safe_mode())       # not in safe_mode — rejected
        results.append(sm2.on_freeze("cv_degraded"))   # FALLBACK — no creative
        sm2.on_safe_mode("operator_manual")
        results.append(activate(sm2, "m1"))            # SAFE_MODE — rejected
        results.append(sm2.on_freeze("cv_degraded"))   # SAFE_MODE — rejected
        return results

    def test_all_transitions_produce_display_action(self):
        for result in self._all_transitions():
            assert result.action in self.VALID_ACTIONS, (
                f"Transition produced blank-screen action: {result}"
            )
