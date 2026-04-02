"""
ICD-2 CvObservation message schema.

This model represents a single observation published to:
  cv/v1/observations/{tenant_id}/{site_id}/{camera_id}

Privacy contract (hard):
- extra="forbid" prevents any unknown field from being set
- ObservationPrivacy fields are always False — no exceptions
- No pixel data, frame URLs, base64 blobs, or face embeddings may appear
  in any field of this model or its serialized JSON output

See: docs/repo-native/authoritative/icd/consolidated-icd-v1.1-csi-local-ingest.md
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Keys that must never appear in any metadata dict or serialized observation.
# Builder enforces this on raw pipeline output; model enforces it structurally.
BANNED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "frame",
        "image",
        "pixels",
        "pixel",
        "base64",
        "embedding",
        "embeddings",
        "face",
        "faces",
        "raw",
        "blob",
        "jpeg",
        "png",
        "thumbnail",
        "snapshot",
        "frame_url",
        "video",
        "clip",
    }
)


class ObservationPrivacy(BaseModel):
    """Hard-false privacy contract flags. Must never be True."""

    model_config = ConfigDict(extra="forbid")

    contains_images: bool = False
    contains_frame_urls: bool = False
    contains_face_embeddings: bool = False

    @model_validator(mode="after")
    def assert_all_false(self) -> ObservationPrivacy:
        if self.contains_images or self.contains_frame_urls or self.contains_face_embeddings:
            raise ValueError(
                "Privacy contract violation: privacy flags must always be False. "
                "No pixel data, frame URLs, or face embeddings are permitted in observations."
            )
        return self


class ObservationCounts(BaseModel):
    """Per-window aggregate counts. No per-identity tracking."""

    model_config = ConfigDict(extra="forbid")

    present: int = Field(ge=0, default=0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class ObservationAttention(BaseModel):
    """
    Head-pose-derived display-engagement estimate over the observation window.
    Behavioral metric — not demographic. Not subject to demographics_suppressed gate.
    Absent when attention_camera_angle_validated=False or head-pose model inactive.
    """

    model_config = ConfigDict(extra="forbid")

    engaged: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ambient: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ObservationDemographics(BaseModel):
    """
    Optional coarse demographic distributions for an observation window.

    Privacy contract:
    - All attributes are probabilistic aggregate bins — no per-person identifiers.
    - gender bins represent coarse visual-appearance classification only.
    - attire bins represent coarse clothing-category classification only.
    - extra="forbid" prevents undeclared fields carrying biometric data.
    """

    model_config = ConfigDict(extra="forbid")

    age_group: Optional[dict[str, float]] = None
    gender: Optional[dict[str, float]] = None
    attire: Optional[dict[str, float]] = None
    dwell_estimate_ms: Optional[int] = Field(default=None, ge=0)
    suppressed: Optional[bool] = None


class CvObservation(BaseModel):
    """
    Single ICD-2 observation message.

    Mirrors the CvObservation schema from Consolidated ICD v1.1.
    extra="forbid" ensures no undeclared field can carry pixel or biometric data.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    message_type: str = Field(default="cv_observation")
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    produced_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tenant_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    pipeline_id: str = Field(min_length=1)
    frame_seq: int = Field(ge=0)
    window_ms: int = Field(ge=0, default=100)
    counts: ObservationCounts = Field(default_factory=ObservationCounts)
    demographics: Optional[ObservationDemographics] = None
    attention: Optional[ObservationAttention] = None
    quality: dict[str, Any] = Field(default_factory=dict)
    privacy: ObservationPrivacy = Field(default_factory=ObservationPrivacy)

    def to_json_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8")
