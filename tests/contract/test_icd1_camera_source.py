"""
ICD-1 contract tests — camera source config (input-cv).

Schema: contracts/input-cv/camera-source.schema.json  v1.1
"""
from __future__ import annotations

import copy

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("input-cv/camera-source.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid() -> dict:
    return {
        "schema_version": "1.1.0",
        "camera_id": "cam-01",
        "source_type": "local_v4l2",
        "device_path": "/dev/video0",
        "enabled": True,
        "pixel_format": "NV12",
        "width": 1920,
        "height": 1080,
        "fps": 30,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidConfig:
    def test_minimal_required_fields(self, valid):
        assert_valid(SCHEMA, valid)

    def test_all_optional_fields(self, valid):
        valid.update({
            "startup_timeout_ms": 5000,
            "read_timeout_ms": 1000,
            "reopen": {
                "enabled": True,
                "initial_backoff_ms": 500,
                "max_backoff_ms": 10000,
            },
            "notes": "bench camera for initial validation",
        })
        assert_valid(SCHEMA, valid)

    @pytest.mark.parametrize("fmt", ["NV12", "YUYV", "MJPG", "RGB3", "BGR3"])
    def test_all_pixel_formats(self, valid, fmt):
        valid["pixel_format"] = fmt
        assert_valid(SCHEMA, valid)

    def test_minimum_resolution(self, valid):
        valid["width"] = 320
        valid["height"] = 240
        assert_valid(SCHEMA, valid)

    def test_maximum_resolution(self, valid):
        valid["width"] = 7680
        valid["height"] = 4320
        assert_valid(SCHEMA, valid)

    def test_fps_extremes(self, valid):
        for fps in (1, 120):
            valid["fps"] = fps
            assert_valid(SCHEMA, valid)

    @pytest.mark.parametrize("cam_id", [
        "cam-01", "CAMERA.1", "site:cam_01", "a" * 128,
    ])
    def test_valid_camera_id_patterns(self, valid, cam_id):
        valid["camera_id"] = cam_id
        assert_valid(SCHEMA, valid)

    def test_enabled_false(self, valid):
        valid["enabled"] = False
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "camera_id", "source_type", "device_path",
        "enabled", "pixel_format", "width", "height", "fps",
    ])
    def test_missing_required_field_rejected(self, valid, field):
        del valid[field]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Schema version enforcement
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_wrong_version_rejected(self, valid):
        valid["schema_version"] = "1.0.0"
        assert_invalid(SCHEMA, valid)

    def test_future_version_rejected(self, valid):
        valid["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# source_type
# ---------------------------------------------------------------------------

class TestSourceType:
    def test_rtsp_rejected(self, valid):
        valid["source_type"] = "rtsp"
        assert_invalid(SCHEMA, valid)

    def test_arbitrary_string_rejected(self, valid):
        valid["source_type"] = "webcam"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# device_path
# ---------------------------------------------------------------------------

class TestDevicePath:
    @pytest.mark.parametrize("path", ["/dev/video0", "/dev/video1", "/dev/video99"])
    def test_valid_device_paths(self, valid, path):
        valid["device_path"] = path
        assert_valid(SCHEMA, valid)

    @pytest.mark.parametrize("path", [
        "/dev/video",      # no digit
        "/dev/videoX",     # letter not digit
        "/dev/v4l/by-id/usb-camera",   # non-standard path
        "video0",          # no /dev/ prefix
    ])
    def test_invalid_device_paths(self, valid, path):
        valid["device_path"] = path
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

class TestNumericBounds:
    def test_width_below_minimum(self, valid):
        valid["width"] = 319
        assert_invalid(SCHEMA, valid)

    def test_height_below_minimum(self, valid):
        valid["height"] = 239
        assert_invalid(SCHEMA, valid)

    def test_fps_zero(self, valid):
        valid["fps"] = 0
        assert_invalid(SCHEMA, valid)

    def test_fps_above_maximum(self, valid):
        valid["fps"] = 121
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_top_level_field_rejected(self, valid):
        valid["raw_image_path"] = "/tmp/frame.jpg"
        assert_invalid(SCHEMA, valid)

    def test_unknown_reopen_field_rejected(self, valid):
        valid["reopen"] = {
            "enabled": True,
            "initial_backoff_ms": 500,
            "max_backoff_ms": 10000,
            "aggressive": True,  # unknown
        }
        assert_invalid(SCHEMA, valid)
