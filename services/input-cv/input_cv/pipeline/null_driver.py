"""
NullDriver: a test stub implementing PipelineDriver.

No GStreamer or pyds imports. Safe to use in any CI environment.

Configurable behaviors:
- raise_on_open: simulate DeviceNotFoundError at open()
- fail_after_n_reads: simulate PipelineReadError after N successful reads
- canned_metadata: the list of dicts returned by read_metadata()
"""
from __future__ import annotations

from .abstract import DeviceNotFoundError, PipelineDriver, PipelineReadError


class NullDriver(PipelineDriver):
    def __init__(
        self,
        raise_on_open: bool = False,
        fail_after_n_reads: int | None = None,
        canned_metadata: list[dict] | None = None,
    ) -> None:
        self.raise_on_open = raise_on_open
        self.fail_after_n_reads = fail_after_n_reads
        self.canned_metadata = canned_metadata or [
            {
                "frame_seq": 0,
                "person_count": 1,
                "confidence_mean": 0.85,
                "frames_processed": 10,
                "frames_dropped": 0,
            }
        ]
        self._read_count = 0
        self.opened = False
        self.closed = False

    def open(self) -> None:
        if self.raise_on_open:
            raise DeviceNotFoundError("NullDriver: simulated missing device")
        self.opened = True
        self._read_count = 0

    def read_metadata(self) -> list[dict]:
        if not self.opened:
            raise RuntimeError("NullDriver: read_metadata called before open()")
        if self.fail_after_n_reads is not None and self._read_count >= self.fail_after_n_reads:
            raise PipelineReadError(
                f"NullDriver: simulated stall after {self.fail_after_n_reads} reads"
            )
        self._read_count += 1
        # Return a copy with incrementing frame_seq
        result = []
        for item in self.canned_metadata:
            entry = dict(item)
            entry["frame_seq"] = entry.get("frame_seq", 0) + self._read_count - 1
            result.append(entry)
        return result

    def close(self) -> None:
        self.opened = False
        self.closed = True
