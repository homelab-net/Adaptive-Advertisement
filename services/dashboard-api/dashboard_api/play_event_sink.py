"""
Player play-event MQTT → play_events DB sink.

Subscribes to the adaptive/play-events/v1 topic published by the player
service on each activate_creative command, and writes append-only impression
rows to the play_events table.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import aiomqtt

from .config import settings
from .db import AsyncSessionLocal
from .models import PlayEvent

log = logging.getLogger(__name__)

_BACKOFF_INITIAL = 2.0
_BACKOFF_MAX = 60.0


def _parse_play_event(payload: bytes) -> PlayEvent | None:
    """
    Parse a play-event MQTT payload into a PlayEvent row.
    Returns None on parse error (message is dropped, not retried).
    """
    try:
        msg = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("play-event-sink: invalid JSON — dropping: %s", exc)
        return None

    try:
        activated_at_raw = msg["activated_at"]
        activated_at = datetime.fromisoformat(activated_at_raw.replace("Z", "+00:00"))

        return PlayEvent(
            id=str(uuid.uuid4()),
            manifest_id=str(msg["manifest_id"])[:128],
            activated_at=activated_at,
            reason=str(msg["reason"])[:256] if msg.get("reason") else None,
            prev_manifest_id=(
                str(msg["prev_manifest_id"])[:128]
                if msg.get("prev_manifest_id")
                else None
            ),
            received_at=datetime.now(timezone.utc),
        )
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("play-event-sink: malformed message — dropping: %s", exc)
        return None


async def run_play_event_sink() -> None:
    """
    Long-running coroutine.  Subscribe to the play-events topic and write
    rows to play_events.  Reconnects with exponential backoff on broker errors.
    """
    topic = settings.mqtt_play_events_topic
    backoff = _BACKOFF_INITIAL
    log.info("play-event-sink starting: broker=%s:%d topic=%s",
             settings.mqtt_broker_host, settings.mqtt_broker_port, topic)

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
            ) as client:
                backoff = _BACKOFF_INITIAL
                log.info("play-event-sink connected to broker")
                await client.subscribe(topic)
                async for message in client.messages:
                    event = _parse_play_event(message.payload)
                    if event is None:
                        continue
                    try:
                        async with AsyncSessionLocal() as session:
                            session.add(event)
                            await session.commit()
                        log.debug(
                            "play-event-sink: wrote event manifest_id=%s", event.manifest_id
                        )
                    except Exception as db_exc:  # noqa: BLE001
                        log.error("play-event-sink: DB write error: %s", db_exc)

        except asyncio.CancelledError:
            log.info("play-event-sink cancelled — exiting")
            return
        except aiomqtt.MqttError as exc:
            log.warning(
                "play-event-sink: broker error: %s — reconnecting in %.0fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "play-event-sink: unexpected error: %s — reconnecting in %.0fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
