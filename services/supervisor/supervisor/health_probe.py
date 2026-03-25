"""
Async HTTP health prober.

Probes a service's /healthz endpoint with a configurable timeout.
Returns a ProbeResult regardless of outcome — never raises.
"""
import time
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    name: str
    url: str
    healthy: bool
    status_code: Optional[int]
    latency_ms: float
    error: Optional[str]


async def probe(
    session: aiohttp.ClientSession,
    name: str,
    url: str,
    timeout_s: float = 5.0,
) -> ProbeResult:
    """
    Probe a single healthz URL.

    healthy=True  when the response status is < 500 (includes 503 readyz failures).
    healthy=False on any connection error, timeout, or 5xx response.
    """
    t0 = time.monotonic()
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout_s),
            allow_redirects=False,
        ) as resp:
            latency_ms = (time.monotonic() - t0) * 1000
            healthy = resp.status < 500
            log.debug(
                "probe name=%s status=%d latency_ms=%.1f healthy=%s",
                name,
                resp.status,
                latency_ms,
                healthy,
            )
            return ProbeResult(
                name=name,
                url=url,
                healthy=healthy,
                status_code=resp.status,
                latency_ms=latency_ms,
                error=None,
            )
    except aiohttp.ClientConnectorError as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        log.debug("probe name=%s connection_error=%s", name, exc)
        return ProbeResult(
            name=name,
            url=url,
            healthy=False,
            status_code=None,
            latency_ms=latency_ms,
            error=f"connection_error: {exc}",
        )
    except aiohttp.ServerTimeoutError as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        log.debug("probe name=%s timeout=%s", name, exc)
        return ProbeResult(
            name=name,
            url=url,
            healthy=False,
            status_code=None,
            latency_ms=latency_ms,
            error=f"timeout: {exc}",
        )
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        log.warning("probe name=%s unexpected_error=%s", name, exc)
        return ProbeResult(
            name=name,
            url=url,
            healthy=False,
            status_code=None,
            latency_ms=latency_ms,
            error=f"error: {exc}",
        )
