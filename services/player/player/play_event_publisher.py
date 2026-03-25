"""
Play-event MQTT publisher.

Publishes a JSON event to adaptive/play-events/v1 each time the player
activates a new creative manifest.  Publishing is fire-and-forget:
failures are logged as warnings but never affect playback.

Privacy: the event contains only manifest_id, timestamps, and operator-set
rationale text.  No audience data, no PII, no image data.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from . import config

log = logging.getLogger(__name__)


class PlayEventPublisher:
    """
    Fire-and-forget MQTT publisher for play events.

    schedule_publish() creates an asyncio task and returns immediately.
    The publish task opens a per-publish MQTT connection, sends the message,
    and closes — no persistent connection is maintained.
    """

    def schedule_publish(
        self,
        manifest_id: str,
        reason: Optional[str],
        prev_manifest_id: Optional[str],
    ) -> None:
        """Schedule a publish; returns immediately (non-blocking)."""
        asyncio.create_task(
            self._publish_task(manifest_id, reason, prev_manifest_id),
            name=f"play-event-publish-{manifest_id}",
        )

    async def _publish_task(
        self,
        manifest_id: str,
        reason: Optional[str],
        prev_manifest_id: Optional[str],
    ) -> None:
        payload = {
            "manifest_id": manifest_id,
            "activated_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "prev_manifest_id": prev_manifest_id,
        }
        try:
            import aiomqtt  # late import — optional dependency
            async with aiomqtt.Client(
                hostname=config.MQTT_BROKER_HOST,
                port=config.MQTT_BROKER_PORT,
            ) as client:
                await client.publish(
                    config.MQTT_PLAY_EVENTS_TOPIC,
                    payload=json.dumps(payload),
                )
            log.debug(
                "play-event published: manifest_id=%s reason=%s", manifest_id, reason
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "play-event publish failed (non-critical): manifest_id=%s error=%s",
                manifest_id, exc,
            )
