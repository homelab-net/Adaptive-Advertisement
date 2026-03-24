"""
Pydantic v2 models mirroring contracts/input-cv/camera-source.schema.json (v1.1.0).

These models are the typed surface for the rest of the service.
The JSON Schema itself is the authoritative contract; loader.py validates
raw JSON against it before constructing these models.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReopenConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    initial_backoff_ms: int = Field(ge=100, le=60000, default=500)
    max_backoff_ms: int = Field(ge=100, le=600000, default=10000)


class CameraSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.1.0"]
    camera_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    source_type: Literal["local_v4l2"]
    device_path: str = Field(pattern=r"^/dev/video[0-9]+$")
    enabled: bool
    pixel_format: Literal["NV12", "YUYV", "MJPG", "RGB3", "BGR3"]
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=240, le=4320)
    fps: int = Field(ge=1, le=120)
    startup_timeout_ms: int = Field(ge=100, le=120000, default=10000)
    read_timeout_ms: int = Field(ge=100, le=120000, default=3000)
    reopen: ReopenConfig = Field(
        default_factory=lambda: ReopenConfig(
            enabled=True, initial_backoff_ms=500, max_backoff_ms=10000
        )
    )
    notes: str = Field(default="", max_length=2000)
