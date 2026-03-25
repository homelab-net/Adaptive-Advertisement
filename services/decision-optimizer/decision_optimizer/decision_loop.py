"""
Decision loop — 1 Hz policy evaluation and command dispatch.

Each tick
---------
1. Assess whether freeze conditions are met (stale signal, degraded pipeline,
   or audience-state service requesting a hold via freeze_decision flag).
2. If freeze → send freeze to player (only once; don't spam).
3. If not frozen → evaluate policy rules against current signal.
4. If candidate manifest changed, OR player was frozen and we're now unfreezing
   → send activate_creative (this also lifts a player freeze per CRM-002).

Freeze reasons (sent to player)
--------------------------------
"cv_degraded"      — source_quality.pipeline_degraded is True
"decision_degraded" — signal_age exceeds stale_signal_threshold_ms
"operator_override" — freeze_decision flag in signal's stability block

The decision loop does NOT send safe_mode — that is the supervisor's authority
(ICD-8). If a supervisor integration is added, it would call
player_gateway.send_safe_mode() directly.

Observability
-------------
status() returns the current loop state for /readyz.
SYS-003: all state transitions are logged.
"""
import asyncio
import logging
import time
from typing import Optional

from . import config
from .policy import PolicyEngine
from .signal_consumer import SignalConsumer
from .player_gateway import PlayerGateway

log = logging.getLogger(__name__)


class DecisionLoop:
    def __init__(
        self,
        policy: PolicyEngine,
        consumer: SignalConsumer,
        gateway: PlayerGateway,
    ) -> None:
        self._policy = policy
        self._consumer = consumer
        self._gateway = gateway

        # Tracked beliefs about player state
        self._current_manifest_id: Optional[str] = None
        self._player_frozen: bool = False

        # Stats
        self._tick_count: int = 0
        self._command_count: int = 0
        self._freeze_count: int = 0

    # ------------------------------------------------------------------
    # Policy hot-swap
    # ------------------------------------------------------------------

    async def reload_policy(self, new_policy: PolicyEngine) -> None:
        """
        Hot-swap the active policy engine.

        Safe without a lock: asyncio is single-threaded; _tick() calls
        policy.evaluate() synchronously with no await, so there is no
        interleaving point where a partial swap could be observed.
        """
        old_count = len(self._policy._rules)
        self._policy = new_policy
        new_count = len(new_policy._rules)
        log.info(
            "policy reloaded: old_rules=%d new_rules=%d", old_count, new_count
        )

    # ------------------------------------------------------------------
    # Run loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Run the decision loop at DECISION_LOOP_HZ until cancelled.
        PERF-004: 1 Hz ±10%.
        """
        interval = 1.0 / config.DECISION_LOOP_HZ
        log.info(
            "decision loop starting: %.1f Hz (interval=%.3fs)", config.DECISION_LOOP_HZ, interval
        )
        while True:
            tick_start = time.monotonic()
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                log.exception("decision loop tick raised unexpected exception — continuing")

            elapsed = time.monotonic() - tick_start
            sleep_for = max(0.0, interval - elapsed)
            await asyncio.sleep(sleep_for)

    # ------------------------------------------------------------------
    # Single tick
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        self._tick_count += 1
        signal = self._consumer.latest_signal
        age_ms = self._consumer.signal_age_ms()

        freeze_reason = self._freeze_reason(signal, age_ms)
        if freeze_reason is not None:
            if not self._player_frozen:
                sent = await self._gateway.send_freeze(freeze_reason)
                self._player_frozen = True
                self._freeze_count += 1
                self._command_count += sent
                log.info(
                    "tick %d: freeze sent reason=%s players=%d",
                    self._tick_count, freeze_reason, sent,
                )
            # Hold — no rule evaluation while frozen
            return

        # Not frozen — evaluate policy
        if signal is None:
            # No signal ever received; stay in whatever state the player is in
            log.debug("tick %d: no signal yet — holding", self._tick_count)
            return

        candidate = self._policy.evaluate(signal)
        if candidate is None:
            log.debug("tick %d: no rule matched — holding", self._tick_count)
            return

        was_frozen = self._player_frozen
        self._player_frozen = False

        # Send activate_creative when manifest changes OR when lifting a freeze
        if candidate != self._current_manifest_id or was_frozen:
            rationale = (
                f"policy rule match; presence_count="
                f"{signal['state']['presence']['count']} "
                f"confidence={signal['state']['presence']['confidence']:.2f}"
            )
            if was_frozen:
                rationale = f"unfreeze + {rationale}"

            sent = await self._gateway.send_activate_creative(
                manifest_id=candidate,
                min_dwell_ms=self._policy.min_dwell_ms,
                cooldown_ms=self._policy.cooldown_ms,
                rationale=rationale,
            )
            self._command_count += sent
            log.info(
                "tick %d: activate_creative manifest=%s was_frozen=%s players=%d",
                self._tick_count, candidate, was_frozen, sent,
            )
            self._current_manifest_id = candidate
        else:
            log.debug(
                "tick %d: manifest unchanged (%s) — no command",
                self._tick_count, candidate,
            )

    # ------------------------------------------------------------------
    # Freeze condition assessment
    # ------------------------------------------------------------------

    def _freeze_reason(
        self, signal: Optional[dict], age_ms: Optional[int]
    ) -> Optional[str]:
        """
        Return a freeze reason string if the player should be frozen, else None.

        Order of checks:
        1. No signal ever received AND it has been more than stale_threshold
           since startup — don't freeze immediately on startup; give the
           audience-state service time to boot.
        2. Signal age exceeds stale threshold.
        3. Upstream pipeline is degraded.
        4. Signal's own freeze_decision flag is set.
        """
        # No signal ever received — don't freeze on startup; give audience-state
        # time to boot. Player stays in FALLBACK until the first command arrives.
        if signal is None:
            return None

        # Check signal age
        if age_ms is not None and age_ms > config.STALE_SIGNAL_THRESHOLD_MS:
            return "decision_degraded"

        # Check upstream pipeline
        if signal.get("source_quality", {}).get("pipeline_degraded", False):
            return "cv_degraded"

        # Check audience-state freeze request
        if signal.get("state", {}).get("stability", {}).get("freeze_decision", False):
            return "operator_override"

        return None

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {
            "current_manifest_id": self._current_manifest_id,
            "player_frozen": self._player_frozen,
            "tick_count": self._tick_count,
            "command_count": self._command_count,
            "freeze_count": self._freeze_count,
            "player_count": self._gateway.player_count,
        }
