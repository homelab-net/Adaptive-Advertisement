"""Shared pytest fixtures for input-cv tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from input_cv.pipeline.null_driver import NullDriver
from input_cv.publisher.null_publisher import NullPublisher


VALID_CONFIG = {
    "schema_version": "1.1.0",
    "camera_id": "cam-test-01",
    "source_type": "local_v4l2",
    "device_path": "/dev/video0",
    "enabled": True,
    "pixel_format": "NV12",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "startup_timeout_ms": 10000,
    "read_timeout_ms": 3000,
    "reopen": {
        "enabled": True,
        "initial_backoff_ms": 500,
        "max_backoff_ms": 10000,
    },
}


@pytest.fixture
def valid_config_dict() -> dict:
    return dict(VALID_CONFIG)


@pytest.fixture
def valid_config_file(valid_config_dict) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as fh:
        json.dump(valid_config_dict, fh)
        return Path(fh.name)


@pytest.fixture
def null_driver() -> NullDriver:
    return NullDriver()


@pytest.fixture
def null_publisher() -> NullPublisher:
    return NullPublisher()
