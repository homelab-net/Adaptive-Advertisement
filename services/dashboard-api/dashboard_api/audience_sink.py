"""
Audience-state MQTT → audience_snapshots DB sink.

Subscribes to the ICD-3 audience-state topic, validates privacy flags,
and writes privacy-safe aggregate rows to the audience_snapshots table.

Privacy enforcement
-------------------
- All ICD-3 privacy flags must be False; messages that set any flag are dropped.
- demographics_suppressed=True → age bin columns written as NULL.
- No message_id, tracking_id, or cross-visit identifiers are persisted.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import aiomqtt

from .config import settings
from .db import AsyncSessionLocal
from .models import AudienceSnapshot

log = logging.getLogger(__name__)

_BACKOFF_INITIAL = 2.0
_BACKOFF_MAX = 60.0


def _parse_snapshot(payload: bytes) -> AudienceSnapshot | None:
    """
    Parse an ICD-3 MQTT payload into an AudienceSnapshot row.
    Returns None on any privacy violation or parse error (message is dropped).
    """
    try:
        msg = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("audience-sink: invalid JSON — dropping: %s", exc)
        return None

    # --- Privacy gate: all flags must be False ---
    privacy = msg.get("privacy", {})
    if (
        privacy.get("contains_images", False)
        or privacy.get("contains_frame_urls", False)
        or privacy.get("contains_face_embeddings", False)
    ):
        log.warning("audience-sink: ICD-3 privacy violation — dropping message")
        return None

    try:
        state = msg["state"]
        presence = state["presence"]
        stability = state.get("stability", {})
        source_quality = msg.get("source_quality", {})

        produced_at_raw = msg.get("produced_at", "")
        sampled_at = datetime.fromisoformat(produced_at_raw.replace("Z", "+00:00"))

        demographics_suppressed: bool = stability.get("demographics_suppressed", True)
        demographics = state.get("demographics", {})
        age_groups = demographics.get("age_groups", {}) if not demographics_suppressed else {}

        return AudienceSnapshot(
            id=str(uuid.uuid4()),
            sampled_at=sampled_at,
            presence_count=int(presence["count"]),
            presence_confidence=float(presence["confidence"]),
            state_stable=bool(stability.get("state_stable", False)),
            pipeline_degraded=bool(source_quality.get("pipeline_degraded", False)),
            demographics_suppressed=demographics_suppressed,
            age_group_child=age_groups.get("child") if age_groups else None,
            age_group_young_adult=age_groups.get("young_adult") if age_groups else None,
            age_group_adult=age_groups.get("adult") if age_groups else None,
            age_group_senior=age_groups.get("senior") if age_groups else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("audience-sink: malformed ICD-3 message — dropping: %s", exc)
        return None


async def run_audience_sink() -> None:
    """
    Long-running coroutine.  Subscribe to the ICD-3 audience-state topic and
    write rows to audience_snapshots.  Reconnects with exponential backoff on
    broker errors.  Cancellation (asyncio.CancelledError) exits cleanly.
    """
    topic = settings.mqtt_audience_state_topic
    backoff = _BACKOFF_INITIAL
    log.info("audience-sink starting: broker=%s:%d topic=%s",
             settings.mqtt_broker_host, settings.mqtt_broker_port, topic)

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
            ) as client:
                backoff = _BACKOFF_INITIAL  # reset on successful connect
                log.info("audience-sink connected to broker")
                await client.subscribe(topic)
                async for message in client.messages:
                    snapshot = _parse_snapshot(message.payload)
                    if snapshot is None:
                        continue
                    try:
                        async with AsyncSessionLocal() as session:
                            session.add(snapshot)
                            await session.commit()
                        log.debug(
                            "audience-sink: wrote snapshot sampled_at=%s count=%d",
                            snapshot.sampled_at.isoformat(), snapshot.presence_count,
                        )
                    except Exception as db_exc:  # noqa: BLE001
                        log.error("audience-sink: DB write error: %s", db_exc)

        except asyncio.CancelledError:
            log.info("audience-sink cancelled — exiting")
            return
        except aiomqtt.MqttError as exc:
            log.warning(
                "audience-sink: broker error: %s — reconnecting in %.0fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "audience-sink: unexpected error: %s — reconnecting in %.0fs", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)
