"""
Integration: mid-stream device failure triggers reopen.

Verifies:
- NullDriver reads succeed up to fail_after_n_reads
- PipelineReadError causes close + reopen attempt
- reopen_count increments
- Subsequent successful reads resume and publish observations
- No banned keys in any published payload
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from input_cv.health import HealthTracker
from input_cv.observation.builder import ObservationContext, build_observation
from input_cv.observation.models import BANNED_METADATA_KEYS
from input_cv.pipeline.null_driver import NullDriver
from input_cv.pipeline.abstract import PipelineReadError
from input_cv.publisher.null_publisher import NullPublisher
from input_cv.recovery.backoff import ReopenLoop

_CONTEXT = ObservationContext(
    tenant_id="t1",
    site_id="s1",
    camera_id="cam-01",
    pipeline_id="p1",
)


def test_stall_triggers_reopen():
    driver = NullDriver(fail_after_n_reads=3)
    health = HealthTracker(camera_id="cam-01", pipeline_id="p1")
    loop = ReopenLoop(
        health=health,
        initial_backoff_ms=100,
        max_backoff_ms=200,
        reopen_enabled=True,
    )

    driver.open()
    health.mark_device_present()

    reads = 0
    stall_caught = False

    with patch("time.sleep"):
        for _ in range(5):
            try:
                driver.read_metadata()
                reads += 1
            except PipelineReadError:
                stall_caught = True
                driver.close()
                health.mark_device_absent()
                loop.wait_and_record()
                break

    assert stall_caught
    assert reads == 3
    assert health.reopen_count == 1


def test_successful_reads_after_reopen_publish_observations():
    publisher = NullPublisher()
    publisher.connect()
    topic = "cv/v1/observations/t1/s1/cam-01"

    # First driver stalls after 2 reads, second driver succeeds
    stalling_driver = NullDriver(fail_after_n_reads=2)
    recovering_driver = NullDriver(fail_after_n_reads=None)

    stalling_driver.open()
    with patch("time.sleep"):
        for _ in range(2):
            meta_list = stalling_driver.read_metadata()
            for meta in meta_list:
                obs = build_observation(meta, _CONTEXT)
                publisher.publish(topic, obs.to_json_bytes())

        try:
            stalling_driver.read_metadata()
        except PipelineReadError:
            stalling_driver.close()

    recovering_driver.open()
    for _ in range(2):
        meta_list = recovering_driver.read_metadata()
        for meta in meta_list:
            obs = build_observation(meta, _CONTEXT)
            publisher.publish(topic, obs.to_json_bytes())

    assert len(publisher.published) == 4


def test_no_banned_keys_in_published_payloads():
    publisher = NullPublisher()
    publisher.connect()
    topic = "cv/v1/observations/t1/s1/cam-01"
    driver = NullDriver()
    driver.open()

    for _ in range(5):
        for meta in driver.read_metadata():
            obs = build_observation(meta, _CONTEXT)
            publisher.publish(topic, obs.to_json_bytes())

    for _, payload in publisher.published:
        parsed = json.loads(payload)
        found = BANNED_METADATA_KEYS & parsed.keys()
        assert not found, f"Banned keys in published payload: {found}"
