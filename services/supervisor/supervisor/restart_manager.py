"""
Restart-ladder logic (ICD-8 / REC-004, REC-006).

Decision rules
--------------
Given a service that has crossed FAILURE_THRESHOLD consecutive failures:

1. If the service is in boot-loop or already escalated → skip (nothing more to do).
2. Prune old restart timestamps (outside the boot-loop detection window).
3. If restarts within the window >= BOOT_LOOP_THRESHOLD → mark boot_loop, return BOOT_LOOP.
4. If total restart_count >= RESTART_THRESHOLD → mark escalated, return ESCALATED.
5. Otherwise → issue docker restart, update state, return RESTARTED.

Boot-loop and escalation are sticky — they do not reset automatically.
Operator intervention (or supervisor restart) is required to clear them.
"""
import asyncio
import logging
import time
from typing import Optional

from .service_table import ManagedService, ServiceState

log = logging.getLogger(__name__)


class RestartDecision:
    RESTARTED = "restarted"
    BOOT_LOOP = "boot_loop"
    ESCALATED = "escalated"
    SKIPPED = "skipped"
    DOCKER_FAILED = "docker_failed"


class RestartManager:
    """
    Decides whether and how to restart a failed service.

    docker_enabled=False disables actual subprocess calls (for tests / dev).
    """

    def __init__(
        self,
        restart_threshold: int,
        fast_fail_window_s: float,
        boot_loop_threshold: int,
        failure_threshold: int = 2,
        docker_enabled: bool = True,
    ) -> None:
        self._restart_threshold = restart_threshold
        self._fast_fail_window = fast_fail_window_s
        self._boot_loop_threshold = boot_loop_threshold
        self._failure_threshold = failure_threshold
        self._docker_enabled = docker_enabled

    async def evaluate(
        self,
        service: ManagedService,
        state: ServiceState,
        now: Optional[float] = None,
    ) -> str:
        """
        Evaluate the restart-ladder for a service that is currently unhealthy.

        Returns a RestartDecision constant.
        Always call this after recording a failure in state.
        """
        # Don't act if the service hasn't crossed the failure threshold yet.
        if state.consecutive_failures < self._failure_threshold:
            return RestartDecision.SKIPPED

        # Stop if already in a terminal escalation state.
        if state.in_boot_loop or state.escalated:
            log.debug(
                "skip restart service=%s boot_loop=%s escalated=%s",
                service.name,
                state.in_boot_loop,
                state.escalated,
            )
            return RestartDecision.SKIPPED

        ts = now if now is not None else time.monotonic()
        state.prune_timestamps(self._fast_fail_window, ts)

        # Boot-loop detection: too many restarts in the recent window.
        if len(state.restart_timestamps) >= self._boot_loop_threshold:
            state.in_boot_loop = True
            log.critical(
                "BOOT LOOP DETECTED service=%s restarts_in_window=%d window_s=%.0f",
                service.name,
                len(state.restart_timestamps),
                self._fast_fail_window,
            )
            return RestartDecision.BOOT_LOOP

        # Hard escalation: total restart count ceiling reached.
        if state.restart_count >= self._restart_threshold:
            state.escalated = True
            log.critical(
                "ESCALATION service=%s restart_count=%d threshold=%d",
                service.name,
                state.restart_count,
                self._restart_threshold,
            )
            return RestartDecision.ESCALATED

        # Attempt restart.
        success = await self._docker_restart(service.container_name)
        if success:
            state.record_restart(ts)
            log.warning(
                "service restarted service=%s restart_count=%d",
                service.name,
                state.restart_count,
            )
            return RestartDecision.RESTARTED
        else:
            return RestartDecision.DOCKER_FAILED

    async def _docker_restart(self, container_name: str) -> bool:
        if not self._docker_enabled:
            log.debug(
                "docker restart disabled (test mode) container=%s", container_name
            )
            return True

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "restart",
                container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            if proc.returncode != 0:
                log.error(
                    "docker restart failed container=%s returncode=%d stderr=%s",
                    container_name,
                    proc.returncode,
                    stderr.decode(errors="replace").strip(),
                )
                return False
            return True
        except asyncio.TimeoutError:
            log.error(
                "docker restart timed out container=%s", container_name
            )
            return False
        except OSError as exc:
            log.error(
                "docker restart OS error container=%s: %s", container_name, exc
            )
            return False
