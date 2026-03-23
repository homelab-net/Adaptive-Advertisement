"""
Health endpoints — OBS-002.

GET /healthz — liveness probe.
    Returns 200 {"status": "ok"} if the process is alive.
    Never returns 5xx under normal conditions.

GET /readyz — readiness probe.
    Returns 200 {"status": "ok", ...state fields} when the player is rendering.
    Returns 503 {"status": "not_ready", "reason": "..."} during startup.

The is_ready flag is a mutable list[bool] so main.py can flip it to True after
the renderer has started and the fallback bundle is confirmed rendering.
"""
import json
import logging

from aiohttp import web

from .state import StateMachine

log = logging.getLogger(__name__)


async def make_health_app(
    state_machine: StateMachine,
    is_ready: list,  # list[bool], index 0
) -> web.Application:
    """
    Create the aiohttp health application.
    is_ready[0] must be set to True by main() after startup completes.
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
        status = state_machine.status()
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok", **status}),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    return app
