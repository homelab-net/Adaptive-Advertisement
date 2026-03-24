"""Config validation — valid inputs."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from input_cv.config import load_camera_config
from input_cv.config.settings import CameraSourceConfig


def _write_config(data: dict) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(data, fh)
        return Path(fh.name)


def test_valid_config_loads(valid_config_dict):
    path = _write_config(valid_config_dict)
    cfg = load_camera_config(path)
    assert isinstance(cfg, CameraSourceConfig)
    assert cfg.camera_id == "cam-test-01"
    assert cfg.schema_version == "1.1.0"
    assert cfg.source_type == "local_v4l2"
    assert cfg.device_path == "/dev/video0"
    assert cfg.enabled is True


def test_schema_version_is_literal(valid_config_dict):
    cfg = CameraSourceConfig.model_validate(valid_config_dict)
    assert cfg.schema_version == "1.1.0"


def test_reopen_defaults_applied(valid_config_dict):
    del valid_config_dict["reopen"]
    cfg = CameraSourceConfig.model_validate(valid_config_dict)
    assert cfg.reopen.enabled is True
    assert cfg.reopen.initial_backoff_ms == 500
    assert cfg.reopen.max_backoff_ms == 10000


def test_optional_notes_default_empty(valid_config_dict):
    cfg = CameraSourceConfig.model_validate(valid_config_dict)
    assert cfg.notes == ""


def test_optional_timeouts_have_defaults(valid_config_dict):
    del valid_config_dict["startup_timeout_ms"]
    del valid_config_dict["read_timeout_ms"]
    cfg = CameraSourceConfig.model_validate(valid_config_dict)
    assert cfg.startup_timeout_ms == 10000
    assert cfg.read_timeout_ms == 3000


def test_all_pixel_formats_accepted(valid_config_dict):
    for fmt in ("NV12", "YUYV", "MJPG", "RGB3", "BGR3"):
        valid_config_dict["pixel_format"] = fmt
        cfg = CameraSourceConfig.model_validate(valid_config_dict)
        assert cfg.pixel_format == fmt


def test_example_config_file_is_valid():
    """The shipped example config must pass validation."""
    example = (
        Path(__file__).parents[2] / "config" / "camera-source.example.json"
    )
    cfg = load_camera_config(example)
    assert cfg.schema_version == "1.1.0"
