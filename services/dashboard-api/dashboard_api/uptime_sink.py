"""
Player uptime probe → uptime_events DB sink.

Periodically probes the player /healthz endpoint and writes a row to
uptime_events for SLO computation.  Uses the existing aiohttp dependency;
no additional packages required.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

import aiohttp

from .config import settings
from .db import AsyncSessionLocal
from .models import UptimeEvent

log = logging.getLogger(__name__)


async def run_uptime_sink() -> None:
    """
    Long-running coroutine.  Probes player /healthz every
    settings.uptime_sample_interval_s seconds and appends a UptimeEvent row.
    """
    interval = settings.uptime_sample_interval_s
    url = settings.player_healthz_url
    log.info("uptime-sink starting: url=%s interval=%.0fs", url, interval)

    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            log.info("uptime-sink cancelled — exiting")
            return

        sampled_at = datetime.now(timezone.utc)
        player_status = "unknown"
        overall_status = "unknown"

        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=settings.health_probe_timeout_s),
                ) as resp:
                    if resp.status == 200:
                        player_status = "healthy"
                        overall_status = "healthy"
                    else:
                        player_status = "unhealthy"
                        overall_status = "degraded"
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            player_status = "unreachable"
            overall_status = "critical"
            log.warning("uptime-sink: player probe failed: %s", exc)
        except asyncio.CancelledError:
            log.info("uptime-sink cancelled during probe — exiting")
            return

        event = UptimeEvent(
            id=str(uuid.uuid4()),
            sampled_at=sampled_at,
            player_status=player_status,
            overall_status=overall_status,
        )
        try:
            async with AsyncSessionLocal() as session:
                session.add(event)
                await session.commit()
            log.debug(
                "uptime-sink: probe recorded player_status=%s", player_status
            )
        except Exception as db_exc:  # noqa: BLE001
            log.error("uptime-sink: DB write error: %s", db_exc)
