"""Config validation — invalid inputs must raise ConfigValidationError."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from input_cv.config.loader import ConfigValidationError, load_camera_config


def _write_config(data: dict) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
        json.dump(data, fh)
        return Path(fh.name)


def _base() -> dict:
    return {
        "schema_version": "1.1.0",
        "camera_id": "cam-test-01",
        "source_type": "local_v4l2",
        "device_path": "/dev/video0",
        "enabled": True,
        "pixel_format": "NV12",
        "width": 1920,
        "height": 1080,
        "fps": 30,
    }


def test_missing_camera_id():
    cfg = _base()
    del cfg["camera_id"]
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_missing_device_path():
    cfg = _base()
    del cfg["device_path"]
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_missing_source_type():
    cfg = _base()
    del cfg["source_type"]
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_wrong_schema_version():
    cfg = _base()
    cfg["schema_version"] = "1.0.0"
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_invalid_source_type():
    cfg = _base()
    cfg["source_type"] = "rtsp"
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_invalid_device_path_pattern():
    cfg = _base()
    cfg["device_path"] = "/dev/camera0"
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_fps_below_minimum():
    cfg = _base()
    cfg["fps"] = 0
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_fps_above_maximum():
    cfg = _base()
    cfg["fps"] = 121
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_width_below_minimum():
    cfg = _base()
    cfg["width"] = 100
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_invalid_pixel_format():
    cfg = _base()
    cfg["pixel_format"] = "H264"
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_additional_properties_rejected():
    cfg = _base()
    cfg["rtsp_url"] = "rtsp://10.0.0.1/stream"
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_reopen_missing_required_subfield():
    cfg = _base()
    cfg["reopen"] = {"enabled": True}  # missing initial_backoff_ms and max_backoff_ms
    with pytest.raises(ConfigValidationError):
        load_camera_config(_write_config(cfg))


def test_not_valid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{")
    with pytest.raises(ConfigValidationError):
        load_camera_config(bad)


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load_camera_config("/nonexistent/path/camera-source.json")
