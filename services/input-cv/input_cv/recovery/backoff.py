"""
Exponential backoff for local-device reopen semantics (ICD-1-CSI-006).

Note on naming: this module uses "reopen" throughout, not "reconnect".
RTSP reconnect concepts do not apply to local V4L2 camera devices.
"""
from __future__ import annotations

import logging
import time

from input_cv.health import HealthTracker

logger = logging.getLogger(__name__)


def next_backoff_seconds(attempt: int, initial_ms: int, max_ms: int) -> float:
    """
    Compute the backoff duration in seconds for a given attempt number.

    attempt=0 returns initial_ms / 1000.0.
    Each subsequent attempt doubles the duration up to max_ms.

    Args:
        attempt: zero-based attempt index.
        initial_ms: starting backoff in milliseconds.
        max_ms: ceiling backoff in milliseconds.

    Returns:
        Backoff duration in seconds (float).
    """
    clamped = min(initial_ms * (2**attempt), max_ms)
    return clamped / 1000.0


class ReopenLoop:
    """
    Manages the reopen cycle for a failed local-device pipeline.

    Calls health.increment_reopen() on each attempt and sleeps
    next_backoff_seconds() between attempts. The caller is responsible
    for actually calling pipeline.open() and handling DeviceNotFoundError.
    """

    def __init__(
        self,
        health: HealthTracker,
        initial_backoff_ms: int,
        max_backoff_ms: int,
        reopen_enabled: bool = True,
    ) -> None:
        self._health = health
        self._initial_ms = initial_backoff_ms
        self._max_ms = max_backoff_ms
        self._enabled = reopen_enabled
        self._attempt = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def wait_and_record(self) -> None:
        """
        Record a reopen attempt in the health tracker and sleep the
        appropriate backoff duration before the next open attempt.
        """
        self._health.increment_reopen()
        delay = next_backoff_seconds(self._attempt, self._initial_ms, self._max_ms)
        logger.warning(
            "input-cv: local device unavailable; reopen attempt %d in %.1fs",
            self._attempt + 1,
            delay,
        )
        time.sleep(delay)
        self._attempt += 1

    def reset(self) -> None:
        """Reset the attempt counter after a successful reopen."""
        self._attempt = 0
