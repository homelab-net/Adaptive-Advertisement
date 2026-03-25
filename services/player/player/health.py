"""
Health endpoints — OBS-002.

GET /healthz — liveness probe.
    Returns 200 {"status": "ok"} if the process is alive.
    Never returns 5xx under normal conditions.

GET /readyz — readiness probe.
    Returns 200 {"status": "ok", ...state fields} when the player is rendering.
    Returns 503 {"status": "not_ready", "reason": "..."} during startup.

POST /control/safe-mode — supervisor injection (ICD-8).
    Body: {"reason": "operator_manual"|"supervisor_escalation"|"boot_loop_protection"}
    Engages safe mode by calling on_safe_mode() on the state machine and invoking
    the on_transition callback.  Returns 200 on success, 503 if not yet ready.

DELETE /control/safe-mode — supervisor injection (ICD-8).
    Clears safe mode.  Returns 200 on success, 503 if not yet ready.

The is_ready flag is a mutable list[bool] so main.py can flip it to True after
the renderer has started and the fallback bundle is confirmed rendering.

The on_transition_holder is a mutable list[Callable|None]; main.py injects
the actual async callback after startup so the control routes can trigger
renderer transitions.
"""
import json
import logging

from aiohttp import web

from adaptive_shared.metrics import aiohttp_metrics_handler

from .state import StateMachine

log = logging.getLogger(__name__)

_VALID_SAFE_MODE_REASONS = {"operator_manual", "supervisor_escalation", "boot_loop_protection"}


async def make_health_app(
    state_machine: StateMachine,
    is_ready: list,          # list[bool], index 0
    on_transition_holder: list,  # list[Callable|None], index 0; injected by main after startup
) -> web.Application:
    """
    Create the aiohttp health application.
    is_ready[0] must be set to True by main() after startup completes.
    on_transition_holder[0] must be set to the on_transition callback by main()
    after the renderer and command handler are wired.
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

    async def safe_mode_engage(request: web.Request) -> web.Response:
        """POST /control/safe-mode — supervisor engages safe mode (ICD-8)."""
        callback = on_transition_holder[0]
        if callback is None or not is_ready[0]:
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"status": "not_ready", "reason": "startup_in_progress"}),
            )
        reason = "operator_manual"
        try:
            body = await request.json()
            candidate = body.get("reason", "operator_manual")
            if candidate in _VALID_SAFE_MODE_REASONS:
                reason = candidate
        except Exception:
            pass  # malformed body: use default reason

        result = state_machine.on_safe_mode(reason)
        await callback(result)
        log.warning(
            "safe mode engaged via supervisor control endpoint reason=%s state=%s",
            reason,
            result.new_state.value,
        )
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok", "state": result.new_state.value}),
        )

    async def safe_mode_clear(request: web.Request) -> web.Response:
        """DELETE /control/safe-mode — supervisor clears safe mode (ICD-8)."""
        callback = on_transition_holder[0]
        if callback is None or not is_ready[0]:
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"status": "not_ready", "reason": "startup_in_progress"}),
            )
        result = state_machine.on_clear_safe_mode()
        await callback(result)
        log.info(
            "safe mode cleared via supervisor control endpoint state=%s",
            result.new_state.value,
        )
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok", "state": result.new_state.value}),
        )

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)
    app.router.add_post("/control/safe-mode", safe_mode_engage)
    app.router.add_delete("/control/safe-mode", safe_mode_clear)
    app.router.add_get("/metrics", aiohttp_metrics_handler)
    return app
