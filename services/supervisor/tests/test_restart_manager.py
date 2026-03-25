"""Tests for RestartManager restart-ladder logic."""
import pytest
import time

from supervisor.service_table import ManagedService, ServiceState
from supervisor.restart_manager import RestartManager, RestartDecision


def _manager(
    restart_threshold: int = 5,
    fast_fail_window: float = 120.0,
    boot_loop_threshold: int = 3,
    failure_threshold: int = 2,
    docker_enabled: bool = False,  # never call docker in unit tests
) -> RestartManager:
    return RestartManager(
        restart_threshold=restart_threshold,
        fast_fail_window_s=fast_fail_window,
        boot_loop_threshold=boot_loop_threshold,
        failure_threshold=failure_threshold,
        docker_enabled=docker_enabled,
    )


@pytest.fixture
def svc() -> ManagedService:
    return ManagedService(
        name="player",
        healthz_url="http://player/healthz",
        container_name="player",
        priority="critical",
    )


@pytest.fixture
def state(svc) -> ServiceState:
    return ServiceState(name=svc.name)


@pytest.mark.asyncio
async def test_skip_below_failure_threshold(svc, state):
    """No restart until failure_threshold consecutive failures."""
    state.consecutive_failures = 1  # below threshold of 2
    mgr = _manager()
    decision = await mgr.evaluate(svc, state)
    assert decision == RestartDecision.SKIPPED


@pytest.mark.asyncio
async def test_restarts_at_threshold(svc, state):
    """Issues restart when consecutive_failures >= failure_threshold."""
    state.consecutive_failures = 2
    mgr = _manager()
    decision = await mgr.evaluate(svc, state)
    assert decision == RestartDecision.RESTARTED
    assert state.restart_count == 1
    assert len(state.restart_timestamps) == 1


@pytest.mark.asyncio
async def test_restart_increments_count(svc, state):
    state.consecutive_failures = 3
    mgr = _manager()
    for expected_count in range(1, 4):
        decision = await mgr.evaluate(svc, state)
        assert decision == RestartDecision.RESTARTED
        assert state.restart_count == expected_count


@pytest.mark.asyncio
async def test_escalation_at_restart_threshold(svc, state):
    """After restart_threshold restarts total, escalate."""
    state.consecutive_failures = 2
    mgr = _manager(restart_threshold=3, boot_loop_threshold=10)
    # Three restarts to fill the threshold.
    for _ in range(3):
        decision = await mgr.evaluate(svc, state)
        assert decision == RestartDecision.RESTARTED
    # Next evaluate → escalated.
    decision = await mgr.evaluate(svc, state)
    assert decision == RestartDecision.ESCALATED
    assert state.escalated is True


@pytest.mark.asyncio
async def test_skipped_when_escalated(svc, state):
    state.escalated = True
    state.consecutive_failures = 10
    mgr = _manager()
    decision = await mgr.evaluate(svc, state)
    assert decision == RestartDecision.SKIPPED


@pytest.mark.asyncio
async def test_boot_loop_detection(svc, state):
    """After BOOT_LOOP_THRESHOLD restarts in the window, the next evaluation detects boot-loop."""
    now = time.monotonic()
    state.consecutive_failures = 2
    mgr = _manager(
        restart_threshold=100,
        fast_fail_window=60.0,
        boot_loop_threshold=3,
    )
    # Perform exactly boot_loop_threshold restarts within the window.
    for _ in range(3):
        decision = await mgr.evaluate(svc, state, now=now)
        assert decision == RestartDecision.RESTARTED
    assert len(state.restart_timestamps) == 3

    # Next evaluation: len(timestamps) == 3 >= boot_loop_threshold → BOOT_LOOP.
    decision = await mgr.evaluate(svc, state, now=now + 1)
    assert decision == RestartDecision.BOOT_LOOP
    assert state.in_boot_loop is True


@pytest.mark.asyncio
async def test_skipped_when_in_boot_loop(svc, state):
    state.in_boot_loop = True
    state.consecutive_failures = 10
    mgr = _manager()
    decision = await mgr.evaluate(svc, state)
    assert decision == RestartDecision.SKIPPED


@pytest.mark.asyncio
async def test_old_timestamps_pruned(svc, state):
    """Timestamps older than the window do not count toward boot-loop."""
    now = time.monotonic()
    window = 60.0
    # Add two very old timestamps (outside the window).
    old_ts = now - window - 10
    state.restart_timestamps = [old_ts, old_ts]
    state.restart_count = 2
    state.consecutive_failures = 2

    mgr = _manager(
        restart_threshold=100,
        fast_fail_window=window,
        boot_loop_threshold=3,
    )
    # Should restart (only 0 timestamps within window after pruning).
    decision = await mgr.evaluate(svc, state, now=now)
    assert decision == RestartDecision.RESTARTED


@pytest.mark.asyncio
async def test_state_record_healthy_resets_failures(state):
    state.record_failure()
    state.record_failure()
    assert state.consecutive_failures == 2
    state.record_healthy()
    assert state.consecutive_failures == 0
    assert state.is_healthy is True


@pytest.mark.asyncio
async def test_state_record_restart_updates_count(state):
    now = 100.0
    state.record_restart(now)
    assert state.restart_count == 1
    assert state.last_restart_at == now
    assert state.restart_timestamps == [now]
