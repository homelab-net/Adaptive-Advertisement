"""
Health endpoints — OBS-002.

GET /healthz — liveness (always 200 if process alive)
GET /readyz  — readiness (200 when startup complete, includes loop + signal status)
"""
import json
import logging

from aiohttp import web

from .decision_loop import DecisionLoop
from .signal_consumer import SignalConsumer
from .player_gateway import PlayerGateway

log = logging.getLogger(__name__)


async def make_health_app(
    loop: DecisionLoop,
    consumer: SignalConsumer,
    gateway: PlayerGateway,
    is_ready: list,  # list[bool], index 0
) -> web.Application:
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
        body = {
            "status": "ok",
            **loop.status(),
            "signal": consumer.status(),
        }
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(body),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    return app
