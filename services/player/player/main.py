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

import aiomqtt
from aiohttp import web
from adaptive_shared.log_config import setup_logging

from . import config
from .fallback import FallbackBundle, FallbackBundleMissingError
from .manifest_store import ManifestStore
from .command_handler import CommandHandler
from .play_event_publisher import PlayEventPublisher
from .renderer import create_renderer, RendererBase, RendererError, RendererStartupError
from .state import StateMachine, TransitionResult, PlayerState
from .health import make_health_app
from .event_publisher import PlayerEventPublisher

setup_logging("player", config.LOG_LEVEL)
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
    on_transition_holder: list = [None]  # injected in step 7 after callback is defined
    health_app = await make_health_app(state_machine, is_ready, on_transition_holder)
    runner = web.AppRunner(health_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    log.info("health server listening port=%d", config.HEALTH_PORT)

    # Step 6: mark ready
    is_ready[0] = True

    # Step 7: command loop

    # ICD-9 event publisher — publishes state transitions to MQTT so that
    # dashboard-api ImpressionRecorder can build impression_events rows.
    event_publisher = PlayerEventPublisher()
    _prev_manifest_id: list[Optional[str]] = [None]  # track for deactivation events

    async def _run_mqtt_client() -> None:
        """
        Background task: maintain MQTT connection for ICD-9 event publishing.

        Reconnects with exponential backoff on broker errors.  Cancelled
        cleanly on shutdown.  Sets/clears the client reference on
        PlayerEventPublisher so publish calls are no-ops while disconnected.
        """
        backoff = 2.0
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=config.MQTT_BROKER_HOST,
                    port=config.MQTT_BROKER_PORT,
                ) as client:
                    backoff = 2.0
                    event_publisher.set_client(client)
                    log.info(
                        "ICD-9 MQTT client connected broker=%s:%d",
                        config.MQTT_BROKER_HOST,
                        config.MQTT_BROKER_PORT,
                    )
                    # Keep the context (and connection) alive until cancelled or error
                    await asyncio.sleep(float("inf"))
            except asyncio.CancelledError:
                event_publisher.clear_client()
                log.info("ICD-9 MQTT client task stopped")
                return
            except aiomqtt.MqttError as exc:
                event_publisher.clear_client()
                log.warning(
                    "ICD-9 MQTT connection lost: %s — reconnecting in %.0fs", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            except Exception as exc:  # noqa: BLE001
                event_publisher.clear_client()
                log.error(
                    "ICD-9 MQTT unexpected error: %s — reconnecting in %.0fs", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    mqtt_task: Optional[asyncio.Task] = None
    if config.MQTT_ENABLED:
        mqtt_task = asyncio.create_task(_run_mqtt_client(), name="icd9-mqtt-client")
        log.info(
            "ICD-9 MQTT event publisher task started (broker=%s:%d)",
            config.MQTT_BROKER_HOST,
            config.MQTT_BROKER_PORT,
        )
    else:
        log.info(
            "ICD-9 event publisher disabled (PLAYER_MQTT_ENABLED=false). "
            "Set to true when Mosquitto broker and ImpressionRecorder are ready."
        )

    async def on_transition(result: TransitionResult) -> None:
        await _execute_transition(result, renderer, fallback, manifest_store)
        # Publish ICD-9 state-transition event for impression tracking
        prev = _prev_manifest_id[0]
        new_state = result.new_state
        if result.action == "play_manifest" and result.manifest_id:
            if prev is not None and prev != result.manifest_id:
                # Previous manifest is being deactivated
                await event_publisher.manifest_deactivated(
                    manifest_id=prev,
                    dwell_elapsed=None,  # dwell state unknown at switch point
                )
            await event_publisher.manifest_activated(
                manifest_id=result.manifest_id,
                rule_rationale=result.reason,
            )
            _prev_manifest_id[0] = result.manifest_id
        elif result.action == "show_fallback":
            if prev is not None:
                if new_state.value == "safe_mode":
                    await event_publisher.safe_mode_entered()
                else:
                    await event_publisher.fallback_entered()
                _prev_manifest_id[0] = None
        elif result.action == "hold" and new_state.value == "frozen":
            await event_publisher.frozen()

    on_transition_holder[0] = on_transition  # expose to supervisor control endpoint (ICD-8)

    play_event_publisher = PlayEventPublisher()

    command_handler = CommandHandler(
        state_machine=state_machine,
        manifest_store=manifest_store,
        on_transition=on_transition,
        play_event_publisher=play_event_publisher,
    )

    # Background task: periodically refresh fallback selection from library
    async def _fallback_refresh_loop() -> None:
        interval = config.FALLBACK_REFRESH_INTERVAL_S
        while True:
            await asyncio.sleep(interval)
            try:
                changed = fallback.refresh()
            except Exception as exc:
                log.warning("fallback refresh error: %s", exc)
                continue
            if changed and state_machine.state.value in ("FALLBACK", "SAFE_MODE"):
                log.info(
                    "fallback asset changed while in %s — updating renderer",
                    state_machine.state.value,
                )
                await renderer.show_fallback(fallback.asset_path)

    # Background task: periodically reload manifest store (full-replace semantics)
    async def _manifest_reload_loop() -> None:
        interval = config.MANIFEST_RELOAD_INTERVAL_S
        while True:
            await asyncio.sleep(interval)
            try:
                manifest_store.reload()
            except Exception as exc:
                log.warning("manifest reload error: %s", exc)

    log.info("player ready — entering command loop")
    refresh_task = asyncio.create_task(_fallback_refresh_loop(), name="fallback-refresh")
    reload_task = asyncio.create_task(_manifest_reload_loop(), name="manifest-reload")
    try:
        await command_handler.run()
    except asyncio.CancelledError:
        log.info("player service shutting down")
    finally:
        refresh_task.cancel()
        reload_task.cancel()
        tasks_to_cancel = [refresh_task, reload_task]
        if mqtt_task is not None:
            mqtt_task.cancel()
            tasks_to_cancel.append(mqtt_task)
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        await renderer.stop()
        await runner.cleanup()
        log.info("player service stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
