"""
adaptive_shared.metrics — Prometheus metrics helpers (OBS-003).

Provides a single generate_metrics_response() call and a ready-made
aiohttp handler.  Services add one route:

    # aiohttp (audience-state, creative, decision-optimizer, player, supervisor)
    app.router.add_get("/metrics", aiohttp_metrics_handler)

    # FastAPI (dashboard-api)
    from fastapi.responses import Response as FastAPIResponse
    from adaptive_shared.metrics import generate_metrics_response
    @router.get("/metrics", include_in_schema=False)
    async def metrics() -> FastAPIResponse:
        body, ctype = generate_metrics_response()
        return FastAPIResponse(content=body, media_type=ctype)

The default prometheus_client registry auto-collects process metrics on
Linux: CPU time, memory RSS/VMS, open file descriptors, GC stats.
No additional instrumentation is required for OBS-003 baseline compliance.
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest


def generate_metrics_response() -> tuple[bytes, str]:
    """Return ``(body_bytes, content_type)`` for a Prometheus /metrics response."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


async def aiohttp_metrics_handler(request):  # type: ignore[no-untyped-def]
    """Drop-in aiohttp GET /metrics handler."""
    from aiohttp import web  # local import keeps this module importable without aiohttp

    body, ctype = generate_metrics_response()
    return web.Response(body=body, headers={"Content-Type": ctype})
