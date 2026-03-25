"""
ImpressionRecorder — MQTT subscriber that builds impression_events rows.

Responsibilities
----------------
1. Subscribe to adaptive-ad/audience/state (ICD-3) — cache latest signal.
2. Subscribe to adaptive-ad/player/events (ICD-9) — detect manifest switches.
3. On manifest_activated: open a new impression row, attach ICD-3 snapshot.
4. On manifest_deactivated / fallback_entered / safe_mode_entered:
   close the open impression with duration + dwell_elapsed + ended_reason.

PLACEHOLDER: MQTT broker connectivity
--------------------------------------
This recorder connects to the same Mosquitto broker used by input-cv,
audience-state, and decision-optimizer. The broker address is configured
via DASHBOARD_MQTT_BROKER_URL (default: mqtt://mosquitto:1883).

The ICD-3 audience/state topic populates once input-cv + audience-state
services are running on Jetson hardware. The ICD-9 player/events topic
populates once the player service publishes event_publisher events on
state transitions. Until both are live, the impression_events table will
remain empty and all analytics endpoints will return data_available=False.

PLACEHOLDER: aiomqtt dependency
---------------------------------
Requires 'aiomqtt' in pyproject.toml. This module is imported at startup
by main.py only if DASHBOARD_MQTT_ENABLED=true (default false for MVP
until hardware is available). If MQTT is disabled, start() returns immediately
and a warning is logged.

Privacy note
------------
Only aggregate metadata is persisted. The ICD-3 schema enforces
privacy.contains_images=false as a const — the subscriber validates this
before writing any audience snapshot fields.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import settings
from .models import ImpressionEvent

log = logging.getLogger(__name__)

# ICD-3 audience-state signal topic (published by audience-state service)
_ICD3_TOPIC = "adaptive-ad/audience/state"

# ICD-9 player event topic (published by player service on state transitions)
# PLACEHOLDER: this topic is defined by ICD-9 (player-event.schema.json).
# The player publishes to this topic in event_publisher.py (player service).
_ICD9_TOPIC = "adaptive-ad/player/events"

# Maximum age of a cached ICD-3 signal before we treat it as stale and
# skip the audience snapshot (record NULL audience fields instead).
_MAX_SIGNAL_AGE_MS = 5_000


class ImpressionRecorder:
    """
    MQTT-driven impression event recorder.

    Instantiate once; call start() from the FastAPI lifespan to begin
    subscribing. Call stop() on shutdown. Uses the same AsyncSession
    factory as the rest of the dashboard-api.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._latest_signal: Optional[dict] = None
        self._latest_signal_at: Optional[float] = None  # monotonic
        # manifest_id → impression row id for the currently-open impression
        self._open_impression_id: Optional[str] = None
        self._open_manifest_id: Optional[str] = None
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Start the MQTT subscriber loop in a background task.

        PLACEHOLDER: MQTT_ENABLED gate
        If DASHBOARD_MQTT_ENABLED is False (default until hardware is ready)
        this method logs a warning and returns without starting the task.
        The impression_events table will remain empty; analytics endpoints
        return data_available=False.
        """
        if not settings.mqtt_enabled:
            log.warning(
                "ImpressionRecorder: MQTT disabled (DASHBOARD_MQTT_ENABLED=false). "
                "Impression data will not be recorded until MQTT is enabled and "
                "ICD-3 + ICD-9 topics are live on the MQTT broker. "
                "Analytics endpoints will return data_available=False."
            )
            return

        self._task = asyncio.create_task(self._run(), name="impression-recorder")
        log.info(
            "ImpressionRecorder started — broker=%s topics=[%s, %s]",
            settings.mqtt_broker_url,
            _ICD3_TOPIC,
            _ICD9_TOPIC,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("ImpressionRecorder stopped")

    # ------------------------------------------------------------------
    # MQTT subscriber loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """
        Main loop: connect to broker, subscribe, dispatch messages.

        PLACEHOLDER: aiomqtt import
        'aiomqtt' must be present in pyproject.toml. If not installed,
        this will raise ImportError at runtime. Add:
            aiomqtt = ">=2.0.0"
        to [project.dependencies] in services/dashboard-api/pyproject.toml
        and rebuild the container.
        """
        try:
            import aiomqtt  # noqa: PLC0415
        except ImportError:
            log.error(
                "ImpressionRecorder: aiomqtt not installed. "
                "Add 'aiomqtt>=2.0.0' to dashboard-api pyproject.toml. "
                "Impression recording is disabled."
            )
            return

        backoff = 2.0
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=settings.mqtt_broker_host,
                    port=settings.mqtt_broker_port,
                    keepalive=30,
                ) as client:
                    backoff = 2.0  # reset on successful connect
                    log.info("ImpressionRecorder: connected to MQTT broker")
                    await client.subscribe(_ICD3_TOPIC, qos=1)
                    await client.subscribe(_ICD9_TOPIC, qos=1)
                    async for message in client.messages:
                        topic = str(message.topic)
                        payload = message.payload
                        if isinstance(payload, (bytes, bytearray)):
                            payload = payload.decode("utf-8", errors="replace")
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            log.warning(
                                "ImpressionRecorder: invalid JSON on %s", topic
                            )
                            continue
                        if topic == _ICD3_TOPIC:
                            self._handle_audience_state(data)
                        elif topic == _ICD9_TOPIC:
                            await self._handle_player_event(data)

            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "ImpressionRecorder: broker error %s — reconnect in %.0fs",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    # ------------------------------------------------------------------
    # ICD-3 audience-state handler
    # ------------------------------------------------------------------

    def _handle_audience_state(self, msg: dict) -> None:
        """
        Cache the latest ICD-3 signal for impression snapshot use.

        Privacy check: ICD-3 schema enforces privacy.contains_images=false
        as a const. We validate that here as a belt-and-suspenders gate.
        """
        privacy = msg.get("privacy", {})
        if (
            privacy.get("contains_images")
            or privacy.get("contains_frame_urls")
            or privacy.get("contains_face_embeddings")
        ):
            # This should never happen (schema const:false) but guard anyway.
            log.error(
                "ICD-3 signal rejected: privacy contract violation — "
                "contains_images/frame_urls/face_embeddings must all be false"
            )
            return

        import time
        self._latest_signal = msg
        self._latest_signal_at = time.monotonic()

    # ------------------------------------------------------------------
    # ICD-9 player event handler
    # ------------------------------------------------------------------

    async def _handle_player_event(self, msg: dict) -> None:
        """
        Dispatch ICD-9 player events to open/close impression rows.

        PLACEHOLDER: ICD-9 schema validation
        Full jsonschema validation against contracts/player/player-event.schema.json
        is omitted here for MVP. Add a jsonschema.Draft202012Validator call
        (matching the pattern in SignalConsumer and PlayerGateway) before the
        first paid pilot.
        """
        event_type = msg.get("event_type")
        manifest_id = msg.get("manifest_id")
        dwell_elapsed = msg.get("dwell_elapsed")
        rule_rationale = msg.get("rule_rationale")

        if event_type == "manifest_activated":
            if manifest_id:
                await self._open_impression(manifest_id, rule_rationale)

        elif event_type == "manifest_deactivated":
            await self._close_impression(
                dwell_elapsed=dwell_elapsed,
                ended_reason="switch",
            )
            # If another manifest is activating, the next manifest_activated
            # event will open the new impression.

        elif event_type in ("fallback_entered",):
            await self._close_impression(
                dwell_elapsed=False,
                ended_reason="disconnect",
            )

        elif event_type == "safe_mode_entered":
            await self._close_impression(
                dwell_elapsed=None,
                ended_reason="safe_mode",
            )

        elif event_type == "frozen":
            await self._close_impression(
                dwell_elapsed=None,
                ended_reason="freeze",
            )

    # ------------------------------------------------------------------
    # Impression open / close
    # ------------------------------------------------------------------

    async def _open_impression(
        self,
        manifest_id: str,
        rule_rationale: Optional[str],
    ) -> None:
        """
        Write a new open impression row for the activating manifest.
        Attaches the latest ICD-3 audience snapshot if fresh enough.
        """
        # Close any previously open impression (shouldn't happen normally,
        # but guard against missed deactivated events on reconnect)
        if self._open_impression_id is not None:
            await self._close_impression(dwell_elapsed=None, ended_reason="unknown")

        # Build audience snapshot from cached ICD-3 signal
        audience_count = None
        audience_confidence = None
        age_child = age_young_adult = age_adult = age_senior = None
        demographics_suppressed = None

        signal = self._latest_signal
        signal_age_ms = self._signal_age_ms()

        if signal is not None and signal_age_ms is not None and signal_age_ms < _MAX_SIGNAL_AGE_MS:
            state = signal.get("state", {})
            presence = state.get("presence", {})
            audience_count = presence.get("count")
            audience_confidence = presence.get("confidence")
            demog = state.get("demographics")
            if demog:
                demographics_suppressed = demog.get("suppressed", False)
                if not demographics_suppressed:
                    age_group = demog.get("age_group", {})
                    age_child = age_group.get("child")
                    age_young_adult = age_group.get("young_adult")
                    age_adult = age_group.get("adult")
                    age_senior = age_group.get("senior")

        impression_id = str(uuid.uuid4())
        async with self._session_factory() as session:
            impression = ImpressionEvent(
                id=impression_id,
                manifest_id=manifest_id,
                rule_rationale=rule_rationale,
                started_at=datetime.now(timezone.utc),
                audience_count=audience_count,
                audience_confidence=audience_confidence,
                age_child=age_child,
                age_young_adult=age_young_adult,
                age_adult=age_adult,
                age_senior=age_senior,
                demographics_suppressed=demographics_suppressed,
            )
            session.add(impression)
            await session.commit()

        self._open_impression_id = impression_id
        self._open_manifest_id = manifest_id
        log.debug(
            "impression opened: id=%s manifest=%s audience_count=%s",
            impression_id,
            manifest_id,
            audience_count,
        )

    async def _close_impression(
        self,
        dwell_elapsed: Optional[bool],
        ended_reason: str,
    ) -> None:
        """
        Close the currently-open impression, computing duration_ms.
        No-op if no impression is open.
        """
        if self._open_impression_id is None:
            return

        ended_at = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            row = await session.get(ImpressionEvent, self._open_impression_id)
            if row is not None and row.ended_at is None:
                row.ended_at = ended_at
                started = row.started_at.replace(tzinfo=timezone.utc) \
                    if row.started_at.tzinfo is None else row.started_at
                row.duration_ms = int(
                    (ended_at - started).total_seconds() * 1000
                )
                row.dwell_elapsed = dwell_elapsed
                row.ended_reason = ended_reason
                await session.commit()
                log.debug(
                    "impression closed: id=%s manifest=%s duration_ms=%d "
                    "dwell=%s reason=%s",
                    self._open_impression_id,
                    self._open_manifest_id,
                    row.duration_ms,
                    dwell_elapsed,
                    ended_reason,
                )

        self._open_impression_id = None
        self._open_manifest_id = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _signal_age_ms(self) -> Optional[int]:
        if self._latest_signal_at is None:
            return None
        import time
        return int((time.monotonic() - self._latest_signal_at) * 1000)

    @property
    def is_live(self) -> bool:
        """True if the MQTT subscriber task is running."""
        return self._task is not None and not self._task.done()

    def status(self) -> dict:
        return {
            "live": self.is_live,
            "open_manifest_id": self._open_manifest_id,
            "signal_age_ms": self._signal_age_ms(),
        }
