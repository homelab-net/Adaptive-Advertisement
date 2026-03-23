"""
Command handler — ICD-4 WebSocket client.

Responsibilities
----------------
1. Connect to decision-optimizer WebSocket with bounded exponential-backoff reconnect.
2. Validate incoming messages against player-command.schema.json (schema_version 1.0.0).
3. Enforce per-session monotonic sequence ordering (reject seq ≤ last_applied).
4. Enforce command idempotency (deduplicate by command_id within session + bounded history).
5. Check manifest approval via ManifestStore before dispatching activate_creative.
6. Dispatch validated commands to the StateMachine.
7. Call on_transition() with every TransitionResult so the caller can execute the
   renderer action.

Session semantics
-----------------
Sequence tracking resets on every reconnect (reset_session). Seen command_id history
is preserved across reconnects to guard against duplicates from the upstream buffer,
but is pruned at MAX_SEEN_IDS to prevent unbounded memory growth.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional

import jsonschema
import websockets
import websockets.exceptions

from . import config
from .state import StateMachine, TransitionResult
from .manifest_store import ManifestStore

log = logging.getLogger(__name__)

_COMMAND_SCHEMA_PATH = (
    Path(config.PLAYER_CONTRACT_DIR) / "player" / "player-command.schema.json"
)

# Maximum number of command_ids retained for idempotency checking.
# At 10 000 entries the dict stays well under 1 MB.
_MAX_SEEN_IDS = 10_000

OnTransition = Callable[[TransitionResult], Awaitable[None]]


def _load_command_schema() -> dict:
    with open(_COMMAND_SCHEMA_PATH) as f:
        return json.load(f)


class CommandHandler:
    """
    ICD-4 command handler. Construct once; call run() to start the WebSocket loop.
    """

    def __init__(
        self,
        state_machine: StateMachine,
        manifest_store: ManifestStore,
        on_transition: OnTransition,
    ) -> None:
        self._sm = state_machine
        self._store = manifest_store
        self._on_transition = on_transition
        self._schema = _load_command_schema()
        self._validator = jsonschema.Draft202012Validator(self._schema)
        self._last_sequence: int = -1
        self._seen_command_ids: dict[str, bool] = {}  # ordered dict for pruning

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_raw(self, raw: str) -> None:
        """
        Parse, validate, and dispatch one raw WebSocket message string.
        Logs and returns silently on any rejection (never raises).
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("command rejected: invalid JSON: %s", exc)
            return

        schema_err = self._validate_schema(msg)
        if schema_err:
            log.error("command rejected: schema validation: %s", schema_err)
            return

        command_id: str = msg["command_id"]
        seq: int = msg["sequence_number"]
        command_type: str = msg["command_type"]

        # Idempotency: already-seen commands are silently acknowledged
        if command_id in self._seen_command_ids:
            log.info(
                "command acknowledged (already applied): command_id=%s", command_id
            )
            return

        # Ordering: reject out-of-order or replayed sequence numbers
        if seq <= self._last_sequence:
            log.warning(
                "command rejected: out-of-order seq=%d last_applied=%d command_id=%s",
                seq,
                self._last_sequence,
                command_id,
            )
            return

        self._record(seq, command_id)
        log.info(
            "command dispatching: type=%s command_id=%s seq=%d",
            command_type,
            command_id,
            seq,
        )

        result: TransitionResult = await self._dispatch(msg, command_type)
        await self._on_transition(result)

    def reset_session(self) -> None:
        """Reset sequence counter for a new WebSocket session."""
        self._last_sequence = -1
        log.info("command handler: session reset (new connection)")

    async def run(self) -> None:
        """
        WebSocket receive loop with automatic reconnect.
        Runs forever; cancel the task to stop.
        """
        backoff = config.WS_RECONNECT_INITIAL_BACKOFF_S
        while True:
            try:
                log.info(
                    "connecting to decision-optimizer: %s",
                    config.DECISION_OPTIMIZER_WS_URL,
                )
                async with websockets.connect(
                    config.DECISION_OPTIMIZER_WS_URL,
                    open_timeout=10,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    backoff = config.WS_RECONNECT_INITIAL_BACKOFF_S  # reset on success
                    log.info("connected to decision-optimizer")
                    self.reset_session()
                    async for raw in ws:
                        await self.handle_raw(raw)

            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
                OSError,
                asyncio.TimeoutError,
            ) as exc:
                log.warning(
                    "WebSocket disconnected: %s — reconnect in %.1fs", exc, backoff
                )
                result = self._sm.on_connection_lost()
                await self._on_transition(result)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, config.WS_RECONNECT_MAX_BACKOFF_S)

            except asyncio.CancelledError:
                log.info("command handler stopped")
                raise

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _dispatch(self, msg: dict, command_type: str) -> TransitionResult:
        if command_type == "activate_creative":
            return self._handle_activate_creative(msg)
        if command_type == "freeze":
            payload = msg.get("freeze") or {}
            return self._sm.on_freeze(payload.get("reason"))
        if command_type == "safe_mode":
            payload = msg.get("safe_mode") or {}
            return self._sm.on_safe_mode(payload.get("reason"))
        if command_type == "clear_safe_mode":
            return self._sm.on_clear_safe_mode()
        # Unreachable — schema enum enforces command_type values
        raise ValueError(f"unknown command_type: {command_type}")

    def _handle_activate_creative(self, msg: dict) -> TransitionResult:
        payload: dict = msg.get("activate_creative") or {}
        manifest_id: str = payload["manifest_id"]
        min_dwell_ms: int = payload["min_dwell_ms"]
        cooldown_ms: int = payload.get("cooldown_ms", 0)
        rationale: Optional[str] = payload.get("rationale")

        manifest = self._store.get(manifest_id)
        if manifest is None:
            log.error(
                "activate_creative rejected: unknown manifest_id=%s", manifest_id
            )
            # Hold current content; do not blank
            from .state import PlayerState, TransitionResult as TR
            return TR(
                accepted=False,
                new_state=self._sm.state,
                action="hold" if self._sm.state != PlayerState.FALLBACK else "show_fallback",
                manifest_id=self._sm.active_manifest_id,
                reason="unknown_manifest",
            )

        rejection = self._store.check_manifest(manifest)
        if rejection:
            log.error(
                "activate_creative rejected: manifest_id=%s check=%s",
                manifest_id,
                rejection,
            )
            from .state import PlayerState, TransitionResult as TR
            return TR(
                accepted=False,
                new_state=self._sm.state,
                action="hold" if self._sm.state != PlayerState.FALLBACK else "show_fallback",
                manifest_id=self._sm.active_manifest_id,
                reason=rejection,
            )

        return self._sm.on_activate_creative(
            manifest_id=manifest_id,
            min_dwell_ms=min_dwell_ms,
            cooldown_ms=cooldown_ms,
            rationale=rationale,
        )

    def _validate_schema(self, msg: dict) -> Optional[str]:
        errors = list(self._validator.iter_errors(msg))
        if not errors:
            return None
        return "; ".join(e.message for e in errors[:3])

    def _record(self, seq: int, command_id: str) -> None:
        self._last_sequence = seq
        self._seen_command_ids[command_id] = True
        if len(self._seen_command_ids) > _MAX_SEEN_IDS:
            # Discard the oldest half by rebuilding from the most-recent keys
            keep = list(self._seen_command_ids.keys())[_MAX_SEEN_IDS // 2:]
            self._seen_command_ids = {k: True for k in keep}
