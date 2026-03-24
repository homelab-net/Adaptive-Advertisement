"""
Health endpoints — /healthz and /readyz.

Consistent with all other services in this repo:
  /healthz  — always 200 (liveness); never fails while process is alive
  /readyz   — 200 only when DB is reachable and startup is complete;
              503 otherwise (readiness)
"""
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from adaptive_shared.metrics import generate_metrics_response

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> JSONResponse:
    """Liveness — always 200."""
    return JSONResponse({"status": "ok"})


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics — OBS-003."""
    body, ctype = generate_metrics_response()
    return Response(content=body, media_type=ctype)


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """
    Readiness — 200 when the database connection is live.
    Returns 503 if the DB cannot be reached.
    """
    from .db import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready", "db": "ok"})
    except Exception as exc:  # noqa: BLE001
        log.warning("readyz: DB not reachable: %s", exc)
        return JSONResponse(
            {"status": "not_ready", "db": str(exc)[:128]},
            status_code=503,
        )
