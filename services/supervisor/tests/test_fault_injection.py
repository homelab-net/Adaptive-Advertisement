"""
Fault injection and stress tests for the supervisor restart-ladder (REC-004,
REC-005, REC-006).

These tests exercise multi-step sequences that cannot be verified by the
individual unit tests:

- Full ladder progression: fail → restart × N → boot-loop → safe-mode
- Critical vs non-critical priority safe-mode gate
- Service recovery mid-sequence resets the ladder
- Multiple simultaneous service failures (independent ladders)
- Boot-loop and escalated flags are sticky (no spurious resets)
- Storage threshold level transitions: normal → warn → critical
- Supervisor-initiated safe-mode is independent of dashboard-initiated
- Coordinator loop correctly feeds restart decisions to the relay

All tests run in-process with docker_enabled=False. No HTTP, no Docker.
"""
from __future__ import annotations

import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from supervisor.service_table import ManagedService, ServiceState
from supervisor.restart_manager import RestartManager, RestartDecision
from supervisor.safe_mode_relay import SafeModeRelay
from supervisor.storage_monitor import check_storage, StorageStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc(name: str = "player", priority: str = "critical") -> ManagedService:
    return ManagedService(
        name=name,
        healthz_url=f"http://{name}/healthz",
        container_name=name,
        priority=priority,
    )


def _state(name: str = "player") -> ServiceState:
    return ServiceState(name=name)


def _manager(
    restart_threshold: int = 5,
    boot_loop_threshold: int = 3,
    fast_fail_window: float = 60.0,
    failure_threshold: int = 2,
) -> RestartManager:
    return RestartManager(
        restart_threshold=restart_threshold,
        fast_fail_window_s=fast_fail_window,
        boot_loop_threshold=boot_loop_threshold,
        failure_threshold=failure_threshold,
        docker_enabled=False,
    )


async def _simulate_failure_cycle(
    mgr: RestartManager,
    svc: ManagedService,
    state: ServiceState,
    n_failures: int,
    now: float | None = None,
) -> list[str]:
    """
    Simulate n_failures consecutive failures, recording a decision each time
    the failure_threshold is crossed. Returns list of decisions issued.
    """
    decisions = []
    t = now or time.monotonic()
    for i in range(n_failures):
        state.record_failure()
        decision = await mgr.evaluate(svc, state, now=t + i * 0.1)
        if decision != RestartDecision.SKIPPED:
            decisions.append(decision)
    return decisions


# ---------------------------------------------------------------------------
# Full ladder progression (REC-004)
# ---------------------------------------------------------------------------

class TestFullLadderProgression:
    """
    Prove the complete restart-ladder sequence:
      failures → RESTARTED × N → BOOT_LOOP → stops restarting
    """

    async def test_ladder_restarts_then_boot_loop(self):
        """
        With boot_loop_threshold=3 and restart_threshold=10:
        after 3 restarts in the window the next evaluate returns BOOT_LOOP.
        Evidence for REC-004 and REC-006.
        """
        mgr = _manager(
            restart_threshold=10,
            boot_loop_threshold=3,
            fast_fail_window=120.0,
            failure_threshold=2,
        )
        svc = _svc()
        state = _state()
        now = time.monotonic()

        # Drive 2 failures to arm the threshold
        for _ in range(2):
            state.record_failure()

        # 3 restarts within window
        for i in range(3):
            d = await mgr.evaluate(svc, state, now=now + i)
            assert d == RestartDecision.RESTARTED, f"Expected RESTARTED, got {d} at step {i}"
        assert state.restart_count == 3

        # 4th evaluate → BOOT_LOOP
        state.record_failure()
        d = await mgr.evaluate(svc, state, now=now + 5)
        assert d == RestartDecision.BOOT_LOOP
        assert state.in_boot_loop is True

    async def test_ladder_restarts_then_escalates(self):
        """
        With restart_threshold=3 and boot_loop_threshold=100:
        after 3 restarts the next evaluate returns ESCALATED.
        Evidence for REC-004.
        """
        mgr = _manager(
            restart_threshold=3,
            boot_loop_threshold=100,
            failure_threshold=2,
        )
        svc = _svc()
        state = _state()
        state.consecutive_failures = 2

        for i in range(3):
            d = await mgr.evaluate(svc, state)
            assert d == RestartDecision.RESTARTED, f"step {i}: expected RESTARTED, got {d}"

        d = await mgr.evaluate(svc, state)
        assert d == RestartDecision.ESCALATED
        assert state.escalated is True

    async def test_boot_loop_sticky_no_more_restarts(self):
        """Once in_boot_loop, every subsequent evaluate is SKIPPED."""
        mgr = _manager(restart_threshold=100, boot_loop_threshold=2, failure_threshold=2)
        svc = _svc()
        state = _state()
        state.consecutive_failures = 2
        now = time.monotonic()

        # Drive to boot-loop
        await mgr.evaluate(svc, state, now=now)
        await mgr.evaluate(svc, state, now=now + 0.1)
        d = await mgr.evaluate(svc, state, now=now + 0.2)
        assert d == RestartDecision.BOOT_LOOP
        assert state.in_boot_loop is True

        # All subsequent evaluates are SKIPPED
        for _ in range(5):
            state.record_failure()
            d = await mgr.evaluate(svc, state)
            assert d == RestartDecision.SKIPPED

    async def test_escalated_sticky_no_more_restarts(self):
        """Once escalated, every subsequent evaluate is SKIPPED."""
        mgr = _manager(restart_threshold=2, boot_loop_threshold=100, failure_threshold=2)
        svc = _svc()
        state = _state()
        state.consecutive_failures = 2

        await mgr.evaluate(svc, state)
        await mgr.evaluate(svc, state)
        d = await mgr.evaluate(svc, state)
        assert d == RestartDecision.ESCALATED

        for _ in range(5):
            state.record_failure()
            d = await mgr.evaluate(svc, state)
            assert d == RestartDecision.SKIPPED


# ---------------------------------------------------------------------------
# Critical service → safe-mode escalation gate (REC-006)
# ---------------------------------------------------------------------------

class TestCriticalServiceSafeModeGate:
    """
    The _health_loop logic: BOOT_LOOP/ESCALATED on a critical service must
    engage safe mode; high/medium priority services must not.
    """

    def _make_relay(self) -> tuple[SafeModeRelay, list]:
        """Return a relay with a captured engage call list."""
        relay = SafeModeRelay(
            dashboard_api_url="http://dashboard-api",
            player_control_url="http://player",
        )
        engaged_calls: list[str] = []

        async def _fake_engage(session, reason="supervisor_escalation"):
            engaged_calls.append(reason)
            relay._engaged_by_supervisor = True
            return True

        relay.engage_safe_mode_supervisor = _fake_engage  # type: ignore[method-assign]
        return relay, engaged_calls

    async def _run_health_step(
        self, svc: ManagedService, state: ServiceState,
        mgr: RestartManager, relay: SafeModeRelay, now: float,
    ) -> str:
        """Simulate one health_loop decision step."""
        state.record_failure()
        decision = await mgr.evaluate(svc, state, now=now)
        if decision in (RestartDecision.BOOT_LOOP, RestartDecision.ESCALATED):
            if svc.priority == "critical":
                await relay.engage_safe_mode_supervisor(
                    session=None, reason="supervisor_escalation"
                )
        return decision

    async def test_critical_boot_loop_engages_safe_mode(self):
        """Player (critical) boot-loop → safe mode engaged. Evidence REC-006."""
        mgr = _manager(restart_threshold=100, boot_loop_threshold=2, failure_threshold=2)
        svc = _svc("player", "critical")
        state = _state("player")
        state.consecutive_failures = 2
        relay, calls = self._make_relay()
        now = time.monotonic()

        # Drive to boot-loop
        await self._run_health_step(svc, state, mgr, relay, now)
        await self._run_health_step(svc, state, mgr, relay, now + 0.1)
        d = await self._run_health_step(svc, state, mgr, relay, now + 0.2)

        assert d == RestartDecision.BOOT_LOOP
        assert len(calls) == 1
        assert calls[0] == "supervisor_escalation"
        assert relay.is_safe_mode_active is True

    async def test_critical_escalation_engages_safe_mode(self):
        """Player (critical) escalation → safe mode engaged."""
        mgr = _manager(restart_threshold=2, boot_loop_threshold=100, failure_threshold=2)
        svc = _svc("player", "critical")
        state = _state("player")
        state.consecutive_failures = 2
        relay, calls = self._make_relay()

        await self._run_health_step(svc, state, mgr, relay, now=0.0)
        await self._run_health_step(svc, state, mgr, relay, now=0.1)
        d = await self._run_health_step(svc, state, mgr, relay, now=0.2)

        assert d == RestartDecision.ESCALATED
        assert len(calls) == 1

    async def test_high_priority_boot_loop_does_not_engage_safe_mode(self):
        """decision-optimizer (high) escalation must NOT auto-engage safe mode."""
        mgr = _manager(restart_threshold=100, boot_loop_threshold=2, failure_threshold=2)
        svc = _svc("decision-optimizer", "high")
        state = _state("decision-optimizer")
        state.consecutive_failures = 2
        relay, calls = self._make_relay()
        now = time.monotonic()

        await self._run_health_step(svc, state, mgr, relay, now)
        await self._run_health_step(svc, state, mgr, relay, now + 0.1)
        d = await self._run_health_step(svc, state, mgr, relay, now + 0.2)

        assert d == RestartDecision.BOOT_LOOP
        assert len(calls) == 0  # safe mode NOT engaged for non-critical
        assert relay.is_safe_mode_active is False

    async def test_medium_priority_escalation_does_not_engage_safe_mode(self):
        """creative (medium) escalation does not touch safe mode."""
        mgr = _manager(restart_threshold=2, boot_loop_threshold=100, failure_threshold=2)
        svc = _svc("creative", "medium")
        state = _state("creative")
        state.consecutive_failures = 2
        relay, calls = self._make_relay()

        for _ in range(3):
            await self._run_health_step(svc, state, mgr, relay, now=0.0)

        assert len(calls) == 0


# ---------------------------------------------------------------------------
# Service recovery resets the ladder (REC-001, REC-002, REC-003)
# ---------------------------------------------------------------------------

class TestServiceRecovery:
    """
    When a service recovers (returns healthy), consecutive_failures resets to 0.
    The ladder re-arms from zero on the next failure — restart_count and
    timestamps are NOT reset (they persist for boot-loop detection).
    """

    async def test_recovery_resets_consecutive_failures(self):
        state = _state()
        state.record_failure()
        state.record_failure()
        assert state.consecutive_failures == 2
        state.record_healthy()
        assert state.consecutive_failures == 0
        assert state.is_healthy is True

    async def test_ladder_rearmed_after_recovery(self):
        """After recovery + new failures, the ladder restarts from scratch."""
        mgr = _manager(restart_threshold=10, boot_loop_threshold=10, failure_threshold=2)
        svc = _svc()
        state = _state()

        # First failure sequence: 2 restarts
        state.consecutive_failures = 2
        await mgr.evaluate(svc, state)  # RESTARTED
        await mgr.evaluate(svc, state)  # RESTARTED
        assert state.restart_count == 2

        # Service recovers
        state.record_healthy()
        assert state.consecutive_failures == 0

        # New failure sequence should still issue restarts
        state.record_failure()
        d = await mgr.evaluate(svc, state)  # still below threshold
        assert d == RestartDecision.SKIPPED  # consecutive_failures=1 < 2

        state.record_failure()
        d = await mgr.evaluate(svc, state)
        assert d == RestartDecision.RESTARTED  # consecutive_failures=2 = threshold
        assert state.restart_count == 3  # cumulative count preserved

    async def test_restart_count_not_reset_by_recovery(self):
        """restart_count persists across recovery events — needed for escalation ceiling."""
        mgr = _manager(restart_threshold=5, boot_loop_threshold=100, failure_threshold=2)
        svc = _svc()
        state = _state()

        # First sequence: 2 restarts, then recover
        state.consecutive_failures = 2
        await mgr.evaluate(svc, state)
        await mgr.evaluate(svc, state)
        assert state.restart_count == 2
        state.record_healthy()

        # Second sequence: 2 more restarts
        state.consecutive_failures = 2
        await mgr.evaluate(svc, state)
        await mgr.evaluate(svc, state)
        assert state.restart_count == 4  # cumulative

    async def test_recovery_after_boot_loop_does_not_reset_flag(self):
        """
        Boot-loop flag is sticky even after record_healthy().
        Operator intervention (supervisor restart) is required to clear it.
        """
        state = _state()
        state.in_boot_loop = True
        state.record_healthy()
        assert state.in_boot_loop is True  # flag persists


# ---------------------------------------------------------------------------
# Multiple simultaneous service failures (independent ladders)
# ---------------------------------------------------------------------------

class TestSimultaneousFailures:
    """Two services can fail independently; their ladders do not interfere."""

    async def test_two_services_fail_independently(self):
        mgr = _manager(restart_threshold=10, boot_loop_threshold=10, failure_threshold=2)
        svc_a = _svc("player", "critical")
        svc_b = _svc("creative", "medium")
        state_a = _state("player")
        state_b = _state("creative")

        state_a.consecutive_failures = 2
        state_b.consecutive_failures = 2

        da = await mgr.evaluate(svc_a, state_a)
        db = await mgr.evaluate(svc_b, state_b)

        assert da == RestartDecision.RESTARTED
        assert db == RestartDecision.RESTARTED
        assert state_a.restart_count == 1
        assert state_b.restart_count == 1

    async def test_one_escalates_other_continues_normally(self):
        """service_a escalating does not affect service_b's ladder."""
        mgr = _manager(restart_threshold=2, boot_loop_threshold=100, failure_threshold=2)
        svc_a = _svc("player", "critical")
        svc_b = _svc("creative", "medium")
        state_a = _state("player")
        state_b = _state("creative")
        state_a.consecutive_failures = 2
        state_b.consecutive_failures = 2

        # Exhaust player's restart budget
        await mgr.evaluate(svc_a, state_a)
        await mgr.evaluate(svc_a, state_a)
        d_a = await mgr.evaluate(svc_a, state_a)
        assert d_a == RestartDecision.ESCALATED
        assert state_a.escalated is True

        # creative still gets normal RESTARTED decisions
        d_b = await mgr.evaluate(svc_b, state_b)
        assert d_b == RestartDecision.RESTARTED
        assert state_b.escalated is False

    async def test_old_window_timestamps_dont_bleed_between_states(self):
        """Each ServiceState has its own restart_timestamps list."""
        state_a = _state("player")
        state_b = _state("creative")
        now = time.monotonic()

        state_a.record_restart(now - 10)
        assert len(state_b.restart_timestamps) == 0


# ---------------------------------------------------------------------------
# Storage threshold level transitions (REC-005)
# ---------------------------------------------------------------------------

class TestStorageThresholds:
    """
    Verify storage monitor produces correct is_warning / is_critical signals
    at and around each threshold.  Uses injected StorageStatus directly to
    avoid filesystem dependency.
    """

    def _status(self, used_pct: float) -> StorageStatus:
        total = 100_000_000_000  # 100 GB
        used = int(total * used_pct / 100)
        return StorageStatus(
            path="/data",
            total_bytes=total,
            used_bytes=used,
            free_bytes=total - used,
            used_pct=used_pct,
            warn_pct=80.0,
            critical_pct=90.0,
        )

    def test_below_warn_threshold(self):
        s = self._status(70.0)
        assert not s.is_warning
        assert not s.is_critical

    def test_at_warn_threshold(self):
        s = self._status(80.0)
        assert s.is_warning
        assert not s.is_critical

    def test_above_warn_below_critical(self):
        s = self._status(85.0)
        assert s.is_warning
        assert not s.is_critical

    def test_at_critical_threshold(self):
        s = self._status(90.0)
        assert s.is_warning  # critical implies warning threshold crossed
        assert s.is_critical

    def test_above_critical_threshold(self):
        s = self._status(95.0)
        assert s.is_critical

    def test_full_disk(self):
        s = self._status(100.0)
        assert s.is_critical
        assert s.free_bytes == 0

    def test_progression_normal_to_warn_to_critical(self):
        """Simulate disk filling up across three check points."""
        levels = [
            (60.0, False, False),
            (82.0, True,  False),
            (91.0, True,  True),
        ]
        for pct, expect_warn, expect_critical in levels:
            s = self._status(pct)
            assert s.is_warning == expect_warn, f"warn mismatch at {pct}%"
            assert s.is_critical == expect_critical, f"critical mismatch at {pct}%"

    def test_custom_thresholds(self):
        """Thresholds are configurable — verify non-default values work."""
        s = StorageStatus(
            path="/data",
            total_bytes=100,
            used_bytes=75,
            free_bytes=25,
            used_pct=75.0,
            warn_pct=70.0,
            critical_pct=80.0,
        )
        assert s.is_warning      # 75 >= 70
        assert not s.is_critical  # 75 < 80

    def test_storage_check_missing_path_returns_zeroed(self):
        """check_storage on a non-existent path returns a zeroed status (no raise)."""
        result = check_storage("/nonexistent/path/that/does/not/exist")
        assert result.total_bytes == 0
        assert result.used_bytes == 0
        assert not result.is_warning
        assert not result.is_critical


# ---------------------------------------------------------------------------
# Safe-mode: supervisor-initiated vs dashboard-initiated independence
# ---------------------------------------------------------------------------

class TestSafeModeIndependence:
    """
    Supervisor-initiated and dashboard-initiated safe mode are independent
    flags.  Either alone activates; clearing one doesn't clear the other.
    """

    def _relay(self) -> SafeModeRelay:
        return SafeModeRelay(
            dashboard_api_url="http://dashboard-api",
            player_control_url="http://player",
        )

    def test_neither_active_by_default(self):
        relay = self._relay()
        assert relay.is_safe_mode_active is False
        assert relay._engaged_by_dashboard is False
        assert relay._engaged_by_supervisor is False

    def test_dashboard_alone_activates(self):
        relay = self._relay()
        relay._engaged_by_dashboard = True
        assert relay.is_safe_mode_active is True

    def test_supervisor_alone_activates(self):
        relay = self._relay()
        relay._engaged_by_supervisor = True
        assert relay.is_safe_mode_active is True

    def test_both_active_simultaneously(self):
        relay = self._relay()
        relay._engaged_by_dashboard = True
        relay._engaged_by_supervisor = True
        assert relay.is_safe_mode_active is True

    def test_clearing_dashboard_does_not_clear_supervisor(self):
        """If supervisor engaged, clearing dashboard leaves safe mode active."""
        relay = self._relay()
        relay._engaged_by_dashboard = True
        relay._engaged_by_supervisor = True
        # Dashboard clears
        relay._engaged_by_dashboard = False
        assert relay.is_safe_mode_active is True  # supervisor flag still set

    def test_clearing_supervisor_does_not_clear_dashboard(self):
        relay = self._relay()
        relay._engaged_by_dashboard = True
        relay._engaged_by_supervisor = True
        relay._engaged_by_supervisor = False
        assert relay.is_safe_mode_active is True  # dashboard still set

    def test_both_cleared_deactivates(self):
        relay = self._relay()
        relay._engaged_by_dashboard = True
        relay._engaged_by_supervisor = True
        relay._engaged_by_dashboard = False
        relay._engaged_by_supervisor = False
        assert relay.is_safe_mode_active is False

    async def test_supervisor_engage_sets_flag(self):
        """engage_safe_mode_supervisor sets _engaged_by_supervisor."""
        relay = self._relay()

        class _OkSession:
            def post(self, url, **kwargs):
                return _OkCtx()

        class _OkCtx:
            async def __aenter__(self):
                class R:
                    status = 200
                return R()
            async def __aexit__(self, *_):
                pass

        ok = await relay.engage_safe_mode_supervisor(_OkSession(), reason="supervisor_escalation")
        assert ok is True
        assert relay._engaged_by_supervisor is True
        assert relay.is_safe_mode_active is True


# ---------------------------------------------------------------------------
# Timestamp pruning in a long-running sequence
# ---------------------------------------------------------------------------

class TestTimestampPruning:
    """
    Old restart timestamps are pruned before boot-loop detection runs.
    This means a service that crashed and recovered long ago should not
    accumulate stale timestamps that inflate the boot-loop count.
    """

    async def test_old_timestamps_dont_count_toward_boot_loop(self):
        mgr = _manager(
            restart_threshold=100,
            boot_loop_threshold=3,
            fast_fail_window=60.0,
            failure_threshold=2,
        )
        svc = _svc()
        state = _state()
        state.consecutive_failures = 2

        now = 1000.0  # fixed reference time

        # Two very old restarts — outside the 60 s window
        state.record_restart(now - 120.0)
        state.record_restart(now - 90.0)
        assert len(state.restart_timestamps) == 2

        # A fresh restart at 'now' — after pruning only this one is in window
        d = await mgr.evaluate(svc, state, now=now)
        assert d == RestartDecision.RESTARTED
        # After evaluate + prune, only the one new timestamp should remain
        state.prune_timestamps(60.0, now)
        assert len(state.restart_timestamps) == 1

    async def test_recovery_after_old_timestamps_does_not_boot_loop(self):
        """Service had old restarts, recovered, now failing again — no false boot-loop."""
        mgr = _manager(
            restart_threshold=100,
            boot_loop_threshold=3,
            fast_fail_window=30.0,
            failure_threshold=2,
        )
        svc = _svc()
        state = _state()

        now = 2000.0
        # Inject 2 old timestamps (outside the 30 s window)
        state.restart_timestamps = [now - 60.0, now - 45.0]
        state.restart_count = 2
        state.consecutive_failures = 2

        # New failure — only 0 timestamps in the window after pruning
        d = await mgr.evaluate(svc, state, now=now)
        assert d == RestartDecision.RESTARTED, f"should restart, not boot-loop; got {d}"
        assert state.in_boot_loop is False
