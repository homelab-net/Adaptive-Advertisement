"""
Player event publisher — ICD-9 MQTT state-transition events.

Publishes a PlayerEvent message to adaptive-ad/player/events on every
state transition so that dashboard-api ImpressionRecorder can build
impression_events rows without polling the player.

The aiomqtt.Client is injected via set_client() after the background
MQTT task connects in main.py.  If no client is set (PLAYER_MQTT_ENABLED=false
or while the broker is unreachable), publish calls are silent no-ops.

Topic
-----
adaptive-ad/player/events   QoS 1 (delivery guaranteed; duplicates possible)
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

log = logging.getLogger(__name__)

_EVENT_TOPIC = "adaptive-ad/player/events"
_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _build_event(
    event_type: str,
    manifest_id: Optional[str] = None,
    dwell_elapsed: Optional[bool] = None,
    rule_rationale: Optional[str] = None,
) -> dict:
    """Build a validated ICD-9 PlayerEvent dict."""
    msg: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "produced_at": _utc_now(),
        "event_type": event_type,
    }
    if manifest_id is not None:
        msg["manifest_id"] = manifest_id
    if dwell_elapsed is not None:
        msg["dwell_elapsed"] = dwell_elapsed
    if rule_rationale is not None:
        msg["rule_rationale"] = rule_rationale

    return msg


class PlayerEventPublisher:
    """
    Publishes ICD-9 PlayerEvent messages to MQTT.

    Pass an aiomqtt.Client instance via set_client() once the MQTT
    connection is established in main.py. If no client is set, publish
    calls are silent no-ops (allows running without MQTT for dev/test).
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None  # aiomqtt.Client once connected
        self._published: int = 0
        self._failed: int = 0

    def set_client(self, client: Any) -> None:
        """Inject the live aiomqtt.Client after MQTT connection is established."""
        self._client = client

    def clear_client(self) -> None:
        """Clear the client reference on MQTT disconnect."""
        self._client = None

    async def manifest_activated(
        self,
        manifest_id: str,
        rule_rationale: Optional[str] = None,
    ) -> None:
        """Publish manifest_activated event."""
        await self._publish(_build_event(
            event_type="manifest_activated",
            manifest_id=manifest_id,
            rule_rationale=rule_rationale,
        ))

    async def manifest_deactivated(
        self,
        manifest_id: str,
        dwell_elapsed: Optional[bool],
    ) -> None:
        """Publish manifest_deactivated event."""
        await self._publish(_build_event(
            event_type="manifest_deactivated",
            manifest_id=manifest_id,
            dwell_elapsed=dwell_elapsed,
        ))

    async def frozen(self) -> None:
        """Publish frozen event (ACTIVE → FROZEN transition)."""
        await self._publish(_build_event(event_type="frozen"))

    async def safe_mode_entered(self) -> None:
        """Publish safe_mode_entered event."""
        await self._publish(_build_event(event_type="safe_mode_entered"))

    async def safe_mode_cleared(self) -> None:
        """Publish safe_mode_cleared event (SAFE_MODE → FALLBACK)."""
        await self._publish(_build_event(event_type="safe_mode_cleared"))

    async def fallback_entered(self) -> None:
        """Publish fallback_entered event (e.g. connection lost → FALLBACK)."""
        await self._publish(_build_event(event_type="fallback_entered"))

    async def _publish(self, event: dict) -> None:
        if self._client is None:
            log.debug(
                "ICD-9 event not published (no MQTT client): event_type=%s",
                event.get("event_type"),
            )
            return
        try:
            await self._client.publish(
                _EVENT_TOPIC, json.dumps(event), qos=1
            )
            self._published += 1
            log.debug(
                "ICD-9 event published: event_type=%s event_id=%s",
                event.get("event_type"),
                event.get("event_id"),
            )
        except Exception as exc:  # noqa: BLE001
            self._failed += 1
            log.warning("ICD-9 event publish failed: %s", exc)

    def status(self) -> dict:
        return {
            "connected": self._client is not None,
            "published": self._published,
            "failed": self._failed,
        }
