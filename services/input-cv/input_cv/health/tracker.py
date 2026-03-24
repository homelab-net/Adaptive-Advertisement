"""
HealthTracker: tracks live device and pipeline state for input-cv.

Health state is used for:
- local operator visibility
- ICD-2 health topic publishing
- supervisor / restart-ladder decisions

Thread-safe: all public methods acquire the internal lock.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class PipelineState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    REOPENING = "reopening"
    FAILED = "failed"


class HealthTracker:
    def __init__(self, camera_id: str, pipeline_id: str) -> None:
        self.camera_id = camera_id
        self.pipeline_id = pipeline_id
        self._lock = threading.Lock()
        self._device_present: bool = False
        self._last_frame_ts: Optional[datetime] = None
        self._last_pipeline_start_ts: Optional[datetime] = None
        self._reopen_count: int = 0
        self._pipeline_state: PipelineState = PipelineState.STARTING

    # --- mutators ---

    def mark_device_present(self) -> None:
        with self._lock:
            self._device_present = True

    def mark_device_absent(self) -> None:
        with self._lock:
            self._device_present = False

    def mark_pipeline_running(self) -> None:
        with self._lock:
            self._pipeline_state = PipelineState.RUNNING
            self._last_pipeline_start_ts = datetime.now(timezone.utc)

    def mark_reopening(self) -> None:
        with self._lock:
            self._pipeline_state = PipelineState.REOPENING

    def mark_failed(self) -> None:
        with self._lock:
            self._pipeline_state = PipelineState.FAILED

    def record_frame(self, ts: Optional[datetime] = None) -> None:
        with self._lock:
            self._last_frame_ts = ts or datetime.now(timezone.utc)

    def increment_reopen(self) -> None:
        with self._lock:
            self._reopen_count += 1
            self._pipeline_state = PipelineState.REOPENING

    # --- accessors ---

    @property
    def device_present(self) -> bool:
        with self._lock:
            return self._device_present

    @property
    def reopen_count(self) -> int:
        with self._lock:
            return self._reopen_count

    @property
    def pipeline_state(self) -> PipelineState:
        with self._lock:
            return self._pipeline_state

    @property
    def last_frame_ts(self) -> Optional[datetime]:
        with self._lock:
            return self._last_frame_ts

    def as_dict(self) -> dict:
        with self._lock:
            return {
                "camera_id": self.camera_id,
                "pipeline_id": self.pipeline_id,
                "device_present": self._device_present,
                "pipeline_state": self._pipeline_state.value,
                "last_frame_ts": (
                    self._last_frame_ts.isoformat() if self._last_frame_ts else None
                ),
                "last_pipeline_start_ts": (
                    self._last_pipeline_start_ts.isoformat()
                    if self._last_pipeline_start_ts
                    else None
                ),
                "reopen_count": self._reopen_count,
            }
