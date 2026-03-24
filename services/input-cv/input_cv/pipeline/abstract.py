"""
PipelineDriver ABC — the testability seam between DeepStream and all other modules.

All modules above this layer (observation, publisher, health, recovery) depend
only on PipelineDriver. They have no direct imports of pyds or GStreamer.

Contract for read_metadata() return value:
  - list of dicts
  - each dict represents one detection window
  - permitted keys: frame_seq, person_count, confidence_mean, pipeline_fps, inference_ms
  - BANNED: frame, image, pixels, base64, embedding, face, raw, blob, jpeg, etc.
  - the pipeline driver is responsible for never producing banned keys;
    builder.py performs a final check as a defense-in-depth measure
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DeviceNotFoundError(RuntimeError):
    """Raised when the configured local camera device is not present at open time."""


class PipelineReadError(RuntimeError):
    """Raised when the pipeline stalls, the device disconnects, or a read timeout occurs."""


class PipelineDriver(ABC):
    """Abstract local-device pipeline driver."""

    @abstractmethod
    def open(self) -> None:
        """
        Initialize and start the pipeline.

        Validates device existence and permissions, configures capture
        parameters, and starts the inference pipeline.

        Raises:
            DeviceNotFoundError: device path does not exist or is not accessible.
            RuntimeError: pipeline initialization failed for another reason.
        """

    @abstractmethod
    def read_metadata(self) -> list[dict]:
        """
        Return metadata from the latest inference window.

        Returns a list of dicts containing aggregate detection results.
        Must never return pixel data, frame URLs, or biometric material.

        Raises:
            PipelineReadError: read timeout, device stall, or hot-unplug.
        """

    @abstractmethod
    def close(self) -> None:
        """Stop the pipeline and release the local device."""
