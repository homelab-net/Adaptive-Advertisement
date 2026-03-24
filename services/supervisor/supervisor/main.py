"""
Supervisor service entry point — ICD-8.

Responsibilities
----------------
1. Health-probe all managed services every HEALTH_POLL_INTERVAL_S seconds.
2. Apply the restart-ladder (restart → boot-loop → escalation) when a service
   is unhealthy for >= FAILURE_THRESHOLD consecutive probes.
3. Relay safe-mode engage/clear from dashboard-api to the player every
   SAFE_MODE_POLL_INTERVAL_S seconds.
4. Monitor storage usage every STORAGE_CHECK_INTERVAL_S seconds (REC-005).
5. Expose /healthz, /readyz, /status via an aiohttp health server.
6. On boot-loop or escalation of a critical service, engage safe mode on
   the player to preserve screen uptime with a safe fallback (REC-006).

Concurrency model
-----------------
Three independent asyncio tasks run forever:
  _health_loop   — probes + restart-ladder
  _safe_mode_relay.run() — safe-mode sync
  _storage_loop  — disk usage checks

If any task crashes (unexpected exception), the process exits so the host
supervisor (systemd or docker restart policy) can recover it.
"""
import asyncio
import logging
import sys

import aiohttp
from aiohttp import web

from adaptive_shared.log_config import setup_logging

from . import config
from .service_table import ManagedService, ServiceState, build_service_table
from .health_probe import probe
from .restart_manager import RestartManager, RestartDecision
from .safe_mode_relay import SafeModeRelay
from .storage_monitor import check_storage
from .health import make_health_app

setup_logging("supervisor", config.LOG_LEVEL)
log = logging.getLogger(__name__)


# ── Health poll loop ───────────────────────────────────────────────────────

async def _health_loop(
    services: list[ManagedService],
    states: dict[str, ServiceState],
    restart_manager: RestartManager,
    safe_mode_relay: SafeModeRelay,
) -> None:
    """Probe all services and apply the restart-ladder on each interval."""
    async with aiohttp.ClientSession() as session:
        while True:
            for svc in services:
                result = await probe(
                    session,
                    svc.name,
                    svc.healthz_url,
                    timeout_s=config.PROBE_TIMEOUT_S,
                )
                state = states[svc.name]

                if result.healthy:
                    if not state.is_healthy:
                        log.info(
                            "service recovered service=%s after %d failure(s)",
                            svc.name,
                            state.consecutive_failures,
                        )
                    state.record_healthy()
                else:
                    state.record_failure()
                    log.warning(
                        "service unhealthy service=%s consecutive=%d error=%s",
                        svc.name,
                        state.consecutive_failures,
                        result.error or f"status={result.status_code}",
                    )

                    decision = await restart_manager.evaluate(svc, state)

                    if decision in (RestartDecision.BOOT_LOOP, RestartDecision.ESCALATED):
                        if svc.priority == "critical":
                            log.critical(
                                "engaging safe mode — critical service %s decision=%s",
                                svc.name,
                                decision,
                            )
                            await safe_mode_relay.engage_safe_mode_supervisor(
                                session=None,
                                reason="supervisor_escalation",
                            )
                        elif svc.priority == "high":
                            log.error(
                                "high-priority service %s %s — safe mode NOT auto-engaged"
                                " (non-critical path); operator intervention required",
                                svc.name,
                                decision,
                            )

            await asyncio.sleep(config.HEALTH_POLL_INTERVAL_S)


# ── Storage monitor loop ───────────────────────────────────────────────────

async def _storage_loop() -> None:
    while True:
        check_storage(
            config.STORAGE_DATA_PATH,
            warn_pct=config.STORAGE_WARN_PCT,
            critical_pct=config.STORAGE_CRITICAL_PCT,
        )
        await asyncio.sleep(config.STORAGE_CHECK_INTERVAL_S)


# ── Main entry point ───────────────────────────────────────────────────────

async def run() -> None:
    log.info("supervisor starting")

    # Build service table and initial states.
    services = build_service_table()
    states: dict[str, ServiceState] = {
        svc.name: ServiceState(name=svc.name) for svc in services
    }

    restart_manager = RestartManager(
        restart_threshold=config.RESTART_THRESHOLD,
        fast_fail_window_s=config.FAST_FAIL_WINDOW_S,
        boot_loop_threshold=config.BOOT_LOOP_THRESHOLD,
        failure_threshold=config.FAILURE_THRESHOLD,
        docker_enabled=config.DOCKER_RESTART_ENABLED,
    )

    safe_mode_relay = SafeModeRelay(
        dashboard_api_url=config.DASHBOARD_API_URL,
        player_control_url=config.PLAYER_CONTROL_URL,
        poll_interval_s=config.SAFE_MODE_POLL_INTERVAL_S,
    )

    # Health server.
    is_ready: list = [False]
    health_app = await make_health_app(states, is_ready)
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("health server listening port=%d", config.HEALTH_PORT)

    is_ready[0] = True
    log.info(
        "supervisor ready managing %d services: %s",
        len(services),
        ", ".join(s.name for s in services),
    )

    # Run all loops concurrently; if any crashes, let the exception propagate
    # so the process exits and the host restart policy recovers it.
    try:
        await asyncio.gather(
            _health_loop(services, states, restart_manager, safe_mode_relay),
            safe_mode_relay.run(),
            _storage_loop(),
        )
    except asyncio.CancelledError:
        log.info("supervisor shutting down")
    finally:
        await runner.cleanup()
        log.info("supervisor stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
