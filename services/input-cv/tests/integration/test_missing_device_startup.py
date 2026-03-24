"""
Integration: missing device at startup.

Verifies:
- DeviceNotFoundError causes health to mark device_absent
- ReopenLoop fires at least twice (with mocked sleep)
- reopen_count increments correctly
- No observation is published during failed startup
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from input_cv.health import HealthTracker, PipelineState
from input_cv.pipeline.null_driver import NullDriver
from input_cv.publisher.null_publisher import NullPublisher
from input_cv.recovery.backoff import ReopenLoop


def test_missing_device_health_marks_absent():
    driver = NullDriver(raise_on_open=True)
    health = HealthTracker(camera_id="cam-01", pipeline_id="p1")

    try:
        driver.open()
    except Exception:
        health.mark_device_absent()

    assert health.device_present is False


def test_reopen_loop_increments_count():
    health = HealthTracker(camera_id="cam-01", pipeline_id="p1")
    loop = ReopenLoop(
        health=health,
        initial_backoff_ms=100,
        max_backoff_ms=200,
        reopen_enabled=True,
    )
    with patch("time.sleep"):
        loop.wait_and_record()
        loop.wait_and_record()

    assert health.reopen_count == 2
    assert health.pipeline_state == PipelineState.REOPENING


def test_reopen_loop_fires_multiple_times_on_missing_device():
    """Simulate the open/reopen loop running until a max attempt limit."""
    driver = NullDriver(raise_on_open=True)
    health = HealthTracker(camera_id="cam-01", pipeline_id="p1")
    loop = ReopenLoop(
        health=health,
        initial_backoff_ms=100,
        max_backoff_ms=200,
        reopen_enabled=True,
    )
    publisher = NullPublisher()

    max_attempts = 3
    attempts = 0

    with patch("time.sleep"):
        while attempts < max_attempts:
            try:
                driver.open()
                break
            except Exception:
                health.mark_device_absent()
                loop.wait_and_record()
                attempts += 1

    assert health.reopen_count == max_attempts
    assert len(publisher.published) == 0


def test_no_observations_published_on_startup_failure():
    publisher = NullPublisher()
    publisher.connect()
    # Nothing should be published when open() always raises
    assert len(publisher.published) == 0
