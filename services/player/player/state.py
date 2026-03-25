"""
Player state machine — pure logic, no I/O.

States
------
FALLBACK  — rendering fallback bundle; waiting for first valid activate_creative
ACTIVE    — rendering an approved manifest
FROZEN    — holding current creative; activate_creative is accepted to lift freeze
SAFE_MODE — rendering fallback bundle; activate_creative ignored until clear_safe_mode

Transitions return a TransitionResult that tells the caller what renderer action to take.
The state machine itself makes no renderer calls.

Never-blank invariant
---------------------
Every transition produces one of three actions:
  "play_manifest" — start playing a specific manifest
  "show_fallback" — display the static fallback bundle
  "hold"          — continue playing current content unchanged

None of these result in a blank screen.

Freeze semantics note (CRM-002)
--------------------------------
ICD-4 defines a "freeze" command but no "unfreeze" command. The command description
says "stop accepting switch commands until unfrozen," but the schema provides no
unfreezing mechanism other than activate_creative.

Implementation decision: activate_creative in FROZEN state is accepted and lifts the
freeze. This is the only practical recovery path given the four-command schema.
Logged in change-resolution-matrix as CRM-002.
"""
import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


class PlayerState(enum.Enum):
    FALLBACK = "fallback"
    ACTIVE = "active"
    FROZEN = "frozen"
    SAFE_MODE = "safe_mode"


@dataclass
class TransitionResult:
    """Result of a state machine transition attempt."""
    accepted: bool
    new_state: PlayerState
    # Renderer action: "play_manifest" | "show_fallback" | "hold"
    action: str
    manifest_id: Optional[str] = None
    reason: Optional[str] = None


class StateMachine:
    """
    Player state machine.

    All methods are synchronous and free of I/O side effects.
    Safe to call from a single asyncio event loop without locking.
    """

    def __init__(self) -> None:
        self._state: PlayerState = PlayerState.FALLBACK
        self._active_manifest_id: Optional[str] = None
        self._activated_at: Optional[float] = None   # monotonic clock
        self._min_dwell_ms: int = 0
        self._freeze_reason: Optional[str] = None
        self._safe_mode_reason: Optional[str] = None
        # manifest_id -> (deactivated_at: float, cooldown_ms: int)
        self._cooldowns: dict[str, tuple[float, int]] = {}

    # ------------------------------------------------------------------
    # Public read-only properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def active_manifest_id(self) -> Optional[str]:
        return self._active_manifest_id

    # ------------------------------------------------------------------
    # Transition methods
    # ------------------------------------------------------------------

    def on_activate_creative(
        self,
        manifest_id: str,
        min_dwell_ms: int,
        cooldown_ms: int = 0,
        rationale: Optional[str] = None,
    ) -> TransitionResult:
        """
        Handle an activate_creative command.

        Rejected (accepted=False) when:
        - player is in SAFE_MODE
        - current creative dwell has not elapsed (ACTIVE state)
        - manifest is in cooldown

        Accepted in FROZEN state — lifts the freeze (see CRM-002).
        """
        if self._state == PlayerState.SAFE_MODE:
            log.warning(
                "activate_creative rejected: in safe_mode manifest_id=%s", manifest_id
            )
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="show_fallback",
                reason="safe_mode",
            )

        # In ACTIVE (not FROZEN) check dwell before allowing switch
        if self._state == PlayerState.ACTIVE and not self._dwell_elapsed():
            log.info(
                "activate_creative deferred: dwell not elapsed "
                "active_manifest=%s candidate=%s",
                self._active_manifest_id,
                manifest_id,
            )
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="hold",
                manifest_id=self._active_manifest_id,
                reason="dwell_not_elapsed",
            )

        if self._in_cooldown(manifest_id):
            log.info(
                "activate_creative rejected: manifest in cooldown manifest_id=%s",
                manifest_id,
            )
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="hold",
                manifest_id=self._active_manifest_id,
                reason="cooldown",
            )

        # Record cooldown for the manifest being deactivated
        if self._active_manifest_id is not None:
            self._cooldowns[self._active_manifest_id] = (
                time.monotonic(),
                self._cooldown_ms_for_active,
            )

        prev_state = self._state
        self._state = PlayerState.ACTIVE
        self._active_manifest_id = manifest_id
        self._activated_at = time.monotonic()
        self._min_dwell_ms = min_dwell_ms
        self._cooldown_ms_for_active = cooldown_ms
        self._freeze_reason = None

        log.info(
            "state transition: %s → ACTIVE manifest_id=%s min_dwell_ms=%d rationale=%s",
            prev_state.value,
            manifest_id,
            min_dwell_ms,
            rationale,
        )
        return TransitionResult(
            accepted=True,
            new_state=PlayerState.ACTIVE,
            action="play_manifest",
            manifest_id=manifest_id,
        )

    def on_freeze(self, reason: Optional[str] = None) -> TransitionResult:
        """
        Handle a freeze command.

        Holds the current creative; ignores activate_creative until lifted.
        Has no effect in SAFE_MODE or FALLBACK (no creative to hold).
        """
        if self._state == PlayerState.SAFE_MODE:
            log.info("freeze ignored: in safe_mode")
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="show_fallback",
                reason="safe_mode",
            )

        if self._state == PlayerState.FALLBACK:
            log.info("freeze received in FALLBACK: no creative to hold")
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="show_fallback",
                reason="no_active_creative",
            )

        if self._state == PlayerState.FROZEN:
            # Update reason but stay frozen
            self._freeze_reason = reason
            log.info("freeze updated: reason=%s", reason)
            return TransitionResult(
                accepted=True,
                new_state=self._state,
                action="hold",
                manifest_id=self._active_manifest_id,
            )

        # ACTIVE → FROZEN
        self._state = PlayerState.FROZEN
        self._freeze_reason = reason
        log.info(
            "state transition: ACTIVE → FROZEN manifest_id=%s reason=%s",
            self._active_manifest_id,
            reason,
        )
        return TransitionResult(
            accepted=True,
            new_state=PlayerState.FROZEN,
            action="hold",
            manifest_id=self._active_manifest_id,
        )

    def on_safe_mode(self, reason: Optional[str] = None) -> TransitionResult:
        """
        Handle a safe_mode command.

        Immediately switches to fallback bundle and ignores activate_creative
        until clear_safe_mode is received. Cannot be overridden by freeze.
        """
        prev_state = self._state
        if self._active_manifest_id is not None:
            self._cooldowns[self._active_manifest_id] = (
                time.monotonic(),
                self._cooldown_ms_for_active,
            )

        self._state = PlayerState.SAFE_MODE
        self._safe_mode_reason = reason
        self._active_manifest_id = None
        self._activated_at = None
        self._freeze_reason = None

        log.warning(
            "state transition: %s → SAFE_MODE reason=%s", prev_state.value, reason
        )
        return TransitionResult(
            accepted=True,
            new_state=PlayerState.SAFE_MODE,
            action="show_fallback",
            reason=reason,
        )

    def on_clear_safe_mode(self) -> TransitionResult:
        """
        Handle a clear_safe_mode command.

        Returns player to FALLBACK state. Has no effect if not in SAFE_MODE.
        """
        if self._state != PlayerState.SAFE_MODE:
            log.info(
                "clear_safe_mode: not in safe_mode (state=%s) — ignored",
                self._state.value,
            )
            return TransitionResult(
                accepted=False,
                new_state=self._state,
                action="hold",
                reason="not_in_safe_mode",
            )

        self._state = PlayerState.FALLBACK
        self._safe_mode_reason = None
        log.info("state transition: SAFE_MODE → FALLBACK")
        return TransitionResult(
            accepted=True,
            new_state=PlayerState.FALLBACK,
            action="show_fallback",
        )

    def on_connection_lost(self) -> TransitionResult:
        """
        Handle WebSocket disconnection from decision-optimizer.

        SAFE_MODE is sticky across reconnects — only clear_safe_mode lifts it.
        All other states revert to FALLBACK (never-blank: fallback bundle plays).
        Also resets sequence tracking for the next session.
        """
        if self._state == PlayerState.SAFE_MODE:
            log.info("connection lost: staying in SAFE_MODE")
            return TransitionResult(
                accepted=True,
                new_state=self._state,
                action="show_fallback",
                reason="connection_lost_in_safe_mode",
            )

        prev_state = self._state
        if self._active_manifest_id is not None:
            self._cooldowns[self._active_manifest_id] = (
                time.monotonic(),
                self._cooldown_ms_for_active,
            )
        self._state = PlayerState.FALLBACK
        self._active_manifest_id = None
        self._activated_at = None
        self._freeze_reason = None

        log.warning(
            "state transition: %s → FALLBACK (connection lost)", prev_state.value
        )
        return TransitionResult(
            accepted=True,
            new_state=PlayerState.FALLBACK,
            action="show_fallback",
            reason="connection_lost",
        )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Return serialisable status dict for /readyz and structured logs."""
        return {
            "state": self._state.value,
            "active_manifest_id": self._active_manifest_id,
            "dwell_elapsed": (
                self._dwell_elapsed() if self._state == PlayerState.ACTIVE else None
            ),
            "freeze_reason": self._freeze_reason,
            "safe_mode_reason": self._safe_mode_reason,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dwell_elapsed(self) -> bool:
        if self._activated_at is None:
            return True
        elapsed_ms = (time.monotonic() - self._activated_at) * 1000
        return elapsed_ms >= self._min_dwell_ms

    def _in_cooldown(self, manifest_id: str) -> bool:
        entry = self._cooldowns.get(manifest_id)
        if entry is None:
            return False
        deactivated_at, cooldown_ms = entry
        elapsed_ms = (time.monotonic() - deactivated_at) * 1000
        return elapsed_ms < cooldown_ms

    # Initialise to avoid AttributeError before first activation
    _cooldown_ms_for_active: int = 0
