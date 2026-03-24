"""
Creative service entry point.

Startup sequence
----------------
1. Load manifests from MANIFEST_DIR — warn but continue if none found.
2. Start aiohttp HTTP server serving the manifest API and health endpoints.
3. Mark ready.
4. Serve until cancelled.

Runtime note
------------
The creative service is stateless after startup — it loads manifests from
disk and serves them. There are no background tasks or MQTT connections.
Hot-reload of manifests (MANIFEST_DIR watch) is future work; for MVP a
restart picks up new manifests written by the dashboard-api.
"""
import asyncio
import logging
import sys
from pathlib import Path

from aiohttp import web

from . import config
from .manifest_store import ManifestStore
from .api import make_app

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


async def run() -> None:
    log.info("creative service starting")

    store = ManifestStore()
    manifest_dir_path = Path(config.MANIFEST_DIR)
    if not manifest_dir_path.exists():
        log.critical(
            "STARTUP ABORTED — MANIFEST_DIR does not exist: %s", config.MANIFEST_DIR
        )
        sys.exit(1)
    if not manifest_dir_path.is_dir():
        log.critical(
            "STARTUP ABORTED — MANIFEST_DIR is not a directory: %s", config.MANIFEST_DIR
        )
        sys.exit(1)

    count = store.load_directory(config.MANIFEST_DIR)
    if count == 0:
        log.warning(
            "no manifests loaded from %s — "
            "service will return 404 for all manifest requests until restarted with manifests",
            config.MANIFEST_DIR,
        )

    status = store.status()
    log.info(
        "manifest store ready: total=%d approved_active=%d load_errors=%d",
        status["total_stored"],
        status["approved_active"],
        status["load_errors"],
    )

    is_ready: list = [False]
    app = make_app(store, is_ready)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.HTTP_HOST, config.HTTP_PORT)
    await site.start()
    log.info("creative HTTP server listening %s:%d", config.HTTP_HOST, config.HTTP_PORT)

    is_ready[0] = True
    log.info("creative service ready")

    try:
        # Run until cancelled
        await asyncio.get_event_loop().create_future()
    except asyncio.CancelledError:
        log.info("creative service shutting down")
    finally:
        await runner.cleanup()
        log.info("creative service stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
