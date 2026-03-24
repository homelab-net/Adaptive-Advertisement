"""HealthTracker state machine tests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from input_cv.health import HealthTracker, PipelineState


@pytest.fixture
def tracker() -> HealthTracker:
    return HealthTracker(camera_id="cam-01", pipeline_id="p1")


def test_initial_state(tracker):
    assert tracker.device_present is False
    assert tracker.reopen_count == 0
    assert tracker.pipeline_state == PipelineState.STARTING
    assert tracker.last_frame_ts is None


def test_mark_device_present(tracker):
    tracker.mark_device_present()
    assert tracker.device_present is True


def test_mark_device_absent(tracker):
    tracker.mark_device_present()
    tracker.mark_device_absent()
    assert tracker.device_present is False


def test_mark_pipeline_running(tracker):
    tracker.mark_pipeline_running()
    assert tracker.pipeline_state == PipelineState.RUNNING


def test_mark_reopening(tracker):
    tracker.mark_reopening()
    assert tracker.pipeline_state == PipelineState.REOPENING


def test_mark_failed(tracker):
    tracker.mark_failed()
    assert tracker.pipeline_state == PipelineState.FAILED


def test_increment_reopen(tracker):
    tracker.increment_reopen()
    assert tracker.reopen_count == 1
    assert tracker.pipeline_state == PipelineState.REOPENING
    tracker.increment_reopen()
    assert tracker.reopen_count == 2


def test_record_frame_sets_timestamp(tracker):
    ts = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
    tracker.record_frame(ts)
    assert tracker.last_frame_ts == ts


def test_record_frame_uses_now_if_no_ts(tracker):
    tracker.record_frame()
    assert tracker.last_frame_ts is not None


def test_as_dict_shape(tracker):
    tracker.mark_device_present()
    tracker.mark_pipeline_running()
    tracker.increment_reopen()
    d = tracker.as_dict()
    assert d["camera_id"] == "cam-01"
    assert d["pipeline_id"] == "p1"
    assert d["device_present"] is True
    assert d["reopen_count"] == 1
    assert "pipeline_state" in d


def test_thread_safety_smoke(tracker):
    import threading
    errors = []

    def worker():
        try:
            for _ in range(100):
                tracker.increment_reopen()
                tracker.mark_device_present()
                _ = tracker.as_dict()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert tracker.reopen_count == 400
