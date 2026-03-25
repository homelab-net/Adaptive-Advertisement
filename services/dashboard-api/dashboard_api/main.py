"""
dashboard-api service entry point.

Startup sequence
----------------
1. Validate DB connectivity — fail fast if database is unreachable on start.
2. Mount routers (manifests, assets, campaigns, system, analytics, health).
3. Expose OpenAPI docs at /docs (FastAPI default; useful over WireGuard VPN).
4. Start uvicorn.

Architecture notes
------------------
- No auth middleware for MVP: WireGuard VPN is the security boundary.
  All admin endpoints are VPN-only (ICD-NET-1, PROV-003).
- CORS is intentionally not configured — the dashboard frontend is served
  from the same device.
- Playback is NOT hard-dependent on this service (SYS-001, REC-003).
  If dashboard-api is restarted, player and decision services continue
  operating with their last known state.
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adaptive_shared.log_config import setup_logging

from .config import settings
from .health import router as health_router
from .routers.manifests import router as manifests_router
from .routers.assets import router as assets_router
from .routers.campaigns import router as campaigns_router
from .routers.system import router as system_router
from .routers.analytics import router as analytics_router
from .routers.fallback import router as fallback_router

setup_logging("dashboard-api", settings.log_level)
log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # --- startup ---
    log.info("dashboard-api starting — db=%s", settings.database_url[:40])
    from .db import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("database connection verified")
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "database not reachable at startup: %s — service will retry via readyz", exc
        )

    yield  # application is running

    # --- shutdown ---
    await engine.dispose()
    log.info("dashboard-api stopped")


def create_app() -> FastAPI:
    """
    Application factory — callable by tests and the uvicorn entry point.
    """
    app = FastAPI(
        title="Adaptive Advertisement — Dashboard API",
        description=(
            "Operator control plane for the privacy-first adaptive retail signage "
            "appliance. Implements ICD-6 (Frontend ↔ API) and ICD-7 (API ↔ PostgreSQL)."
        ),
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS — localhost only for MVP (dashboard is same-device)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router)
    app.include_router(manifests_router)
    app.include_router(assets_router)
    app.include_router(campaigns_router)
    app.include_router(system_router)
    app.include_router(analytics_router)
    app.include_router(fallback_router)

    return app


def main() -> None:
    app = create_app()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
