"""
Health endpoints — OBS-002.

GET  /healthz           — liveness (always 200 if process alive)
GET  /readyz            — readiness (200 when startup complete, includes loop + signal status)
POST /api/v1/rules/reload — hot-swap policy rules from disk
"""
import json
import logging

from aiohttp import web

from adaptive_shared.metrics import aiohttp_metrics_handler

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

    async def rules_reload(request: web.Request) -> web.Response:
        """
        Hot-swap policy rules from the configured rules file.

        Loads a fresh PolicyEngine from RULES_FILE and calls
        loop.reload_policy() — safe without a lock (single asyncio thread).
        Returns old and new rule counts for observability.
        """
        from . import config
        from .policy import load_policy

        old_count = len(loop._policy._rules)
        try:
            new_policy = load_policy(config.RULES_FILE)
        except (FileNotFoundError, ValueError) as exc:
            log.error("rules reload failed: %s", exc)
            return web.Response(
                status=400,
                content_type="application/json",
                text=json.dumps({"status": "error", "detail": str(exc)}),
            )

        await loop.reload_policy(new_policy)
        new_count = len(new_policy._rules)
        log.info("rules reload: old=%d new=%d", old_count, new_count)
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({
                "status": "ok",
                "old_rule_count": old_count,
                "new_rule_count": new_count,
            }),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", aiohttp_metrics_handler)
    app.router.add_post("/api/v1/rules/reload", rules_reload)
    return app
