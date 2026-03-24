"""
Supervisor health endpoints — OBS-002.

GET /healthz — liveness probe.  Always 200 while the process is running.

GET /readyz  — readiness probe.  200 once all startup tasks have completed.
               Returns a summary of managed-service health as observed on the
               last poll cycle.

GET /status  — detailed health report for all managed services.
               Returns the most recent ServiceState for each service as JSON.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict

from aiohttp import web

from .service_table import ServiceState

log = logging.getLogger(__name__)


def _format_ts(monotonic_ts: float) -> str:
    """Convert a monotonic timestamp offset into an approximate ISO-8601 wall-clock string."""
    now_wall = datetime.now(timezone.utc)
    now_mono = time.monotonic()
    delta = now_mono - monotonic_ts
    approx = now_wall.timestamp() - delta
    return datetime.fromtimestamp(approx, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"


async def make_health_app(
    service_states: Dict[str, ServiceState],
    is_ready: list,  # list[bool], index 0
) -> web.Application:
    """
    Create the supervisor health application.
    service_states is the live dict maintained by the main loop.
    """
    app = web.Application()

    async def healthz(request: web.Request) -> web.Response:
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok"}),
        )

    async def readyz(request: web.Request) -> web.Response:
        if not is_ready[0]:
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"status": "not_ready", "reason": "startup_in_progress"}),
            )
        unhealthy = [
            name
            for name, s in service_states.items()
            if not s.is_healthy
        ]
        body = {"status": "ok"}
        if unhealthy:
            body["degraded_services"] = unhealthy
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(body),
        )

    async def status(request: web.Request) -> web.Response:
        report = {}
        for name, s in service_states.items():
            report[name] = {
                "is_healthy": s.is_healthy,
                "consecutive_failures": s.consecutive_failures,
                "restart_count": s.restart_count,
                "in_boot_loop": s.in_boot_loop,
                "escalated": s.escalated,
                "last_restart_at": (
                    _format_ts(s.last_restart_at)
                    if s.last_restart_at is not None
                    else None
                ),
            }
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"schema_version": "1.0.0", "services": report}),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/status", status)
    return app
