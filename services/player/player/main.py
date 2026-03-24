"""
Player service entry point.

Startup sequence (order is non-negotiable — never-blank invariant)
------------------------------------------------------------------
1. Validate fallback bundle — abort immediately if missing (PERF-006, SYS-001).
2. Initialise state machine (starts in FALLBACK).
3. Start renderer backend; show fallback bundle — screen is live from this point.
4. Load approved manifests from disk.
5. Start health server (/healthz, /readyz).
6. Set is_ready flag — /readyz starts returning 200.
7. Enter WebSocket command loop (reconnects automatically).

If step 1 fails: process exits with code 1. No renderer call is made.
If step 3 fails: process exits with code 1. This preserves PERF-006 intent —
  better to fail fast on startup than to silently run without a display.

The command loop (step 7) runs until the task is cancelled.
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from aiohttp import web

from . import config
from .fallback import FallbackBundle, FallbackBundleMissingError
from .manifest_store import ManifestStore
from .command_handler import CommandHandler
from .renderer import create_renderer, RendererBase, RendererError, RendererStartupError
from .state import StateMachine, TransitionResult, PlayerState
from .health import make_health_app

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Renderer action executor
# ------------------------------------------------------------------

async def _execute_transition(
    result: TransitionResult,
    renderer: RendererBase,
    fallback: FallbackBundle,
    manifest_store: ManifestStore,
) -> None:
    """
    Execute the renderer action indicated by a state machine TransitionResult.

    "show_fallback" — always safe; fallback.asset_path is pre-validated.
    "play_manifest" — resolves manifest items from store; falls back if resolution fails.
    "hold"          — no renderer call; current content continues playing.
    """
    if result.action == "show_fallback":
        await renderer.show_fallback(fallback.asset_path)

    elif result.action == "play_manifest":
        manifest_id: Optional[str] = result.manifest_id
        if manifest_id is None:
            log.error("play_manifest action with no manifest_id — showing fallback")
            await renderer.show_fallback(fallback.asset_path)
            return

        manifest = manifest_store.get(manifest_id)
        if manifest is None:
            log.error(
                "manifest not in store at render time manifest_id=%s — showing fallback",
                manifest_id,
            )
            await renderer.show_fallback(fallback.asset_path)
            return

        items = manifest.get("items") or []
        if not items:
            log.error(
                "manifest has no items manifest_id=%s — showing fallback", manifest_id
            )
            await renderer.show_fallback(fallback.asset_path)
            return

        # MVP: play first item. Multi-item sequencing is out of scope for scaffold.
        item = items[0]
        asset_path = str(Path(config.ASSET_CACHE_PATH) / item["asset_id"])
        try:
            await renderer.play_manifest_item(
                asset_path=asset_path,
                asset_type=item["asset_type"],
                duration_ms=item["duration_ms"],
                loop=item.get("loop", False),
            )
        except RendererError as exc:
            log.error(
                "renderer failed during play_manifest manifest_id=%s: %s — showing fallback",
                manifest_id,
                exc,
            )
            await renderer.show_fallback(fallback.asset_path)

    elif result.action == "hold":
        # Nothing to do — renderer continues playing current content
        pass

    else:
        log.error("unknown renderer action=%r — showing fallback as safety net", result.action)
        await renderer.show_fallback(fallback.asset_path)


# ------------------------------------------------------------------
# Main async entry point
# ------------------------------------------------------------------

async def run() -> None:
    log.info("player service starting")

    # Step 1: validate fallback bundle — abort before touching display
    fallback = FallbackBundle()
    try:
        fallback.validate()
    except FallbackBundleMissingError as exc:
        log.critical("STARTUP ABORTED — fallback bundle missing: %s", exc)
        sys.exit(1)

    # Step 2: state machine
    state_machine = StateMachine()

    # Step 3: renderer — show fallback immediately
    renderer = create_renderer()
    try:
        await renderer.startup()
    except RendererStartupError as exc:
        log.critical("STARTUP ABORTED — renderer failed: %s", exc)
        sys.exit(1)

    await renderer.show_fallback(fallback.asset_path)
    log.info(
        "fallback bundle rendering — player state=%s (PERF-006 satisfied)",
        state_machine.state.value,
    )

    # Step 4: manifests
    manifest_store = ManifestStore()
    manifest_store.load_from_disk()

    # Step 5: health server
    is_ready: list = [False]
    health_app = await make_health_app(state_machine, is_ready)
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("health server listening port=%d", config.HEALTH_PORT)

    # Step 6: mark ready
    is_ready[0] = True

    # Step 7: command loop
    async def on_transition(result: TransitionResult) -> None:
        await _execute_transition(result, renderer, fallback, manifest_store)

    command_handler = CommandHandler(
        state_machine=state_machine,
        manifest_store=manifest_store,
        on_transition=on_transition,
    )

    log.info("player ready — entering command loop")
    try:
        await command_handler.run()
    except asyncio.CancelledError:
        log.info("player service shutting down")
    finally:
        await renderer.stop()
        await runner.cleanup()
        log.info("player service stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
