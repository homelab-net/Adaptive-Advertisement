"""
input-cv health server — OBS-002, OBS-003.

Provides /healthz, /readyz, and /metrics HTTP endpoints.

Since input-cv runs a blocking synchronous main loop (paho-mqtt + while-loop),
the health server runs in a dedicated daemon thread with its own asyncio event
loop so it never competes with the camera read loop.

Usage in main.py::

    from input_cv.health.server import HealthServer

    health = HealthTracker(camera_id=..., pipeline_id=...)
    server = HealthServer(health, port=8006)
    server.start()
    ...
    server.mark_ready()   # called once publisher.connect() succeeds
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from aiohttp import web

from adaptive_shared.metrics import aiohttp_metrics_handler

from .tracker import HealthTracker

log = logging.getLogger(__name__)


def make_health_app(health: HealthTracker, is_ready: list) -> web.Application:
    """
    Build the aiohttp Application.

    Extracted so unit tests can create the app directly without spinning up
    a TCP listener (same pattern as audience-state/health.py).
    """
    app = web.Application()

    async def healthz(_: web.Request) -> web.Response:
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok"}),
        )

    async def readyz(_: web.Request) -> web.Response:
        if not is_ready[0]:
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"status": "not_ready", "reason": "startup_in_progress"}),
            )
        body = {"status": "ok", **health.as_dict()}
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(body),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_get("/metrics", aiohttp_metrics_handler)
    return app


class HealthServer:
    """
    Runs the input-cv health HTTP server in a daemon background thread.

    The thread owns a private asyncio event loop so it does not interfere
    with the synchronous camera read loop on the main thread.
    """

    def __init__(self, health: HealthTracker, port: int) -> None:
        self._health = health
        self._port = port
        self._is_ready: list = [False]
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the health server thread (non-blocking)."""
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="input-cv-health"
        )
        self._thread.start()
        log.info("input-cv: health server thread started port=%d", self._port)

    def mark_ready(self) -> None:
        """Signal that the service has completed startup (/readyz → 200)."""
        self._is_ready[0] = True

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        app = make_health_app(self._health, self._is_ready)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        log.info("input-cv: health server listening port=%d", self._port)
        # Block the daemon thread's event loop indefinitely.
        # The thread exits when the main process exits (daemon=True).
        await asyncio.Event().wait()
