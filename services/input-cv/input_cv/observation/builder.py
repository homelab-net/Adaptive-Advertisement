"""
Build CvObservation messages from raw pipeline metadata dicts.

The builder is the privacy enforcement point between the pipeline driver
(which produces raw detection metadata) and the publisher (which emits
messages downstream).

Two layers of privacy protection:
1. BANNED_METADATA_KEYS check on the raw dict from the pipeline.
2. CvObservation model's extra="forbid" and ObservationPrivacy model_validator.

If either check fails, PrivacyViolationError is raised and no message is
published. This ensures no pixel or biometric data can reach the MQTT broker.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import BANNED_METADATA_KEYS, CvObservation, ObservationCounts


class PrivacyViolationError(RuntimeError):
    """Raised when raw pipeline metadata contains a banned key."""


@dataclass(frozen=True)
class ObservationContext:
    tenant_id: str
    site_id: str
    camera_id: str
    pipeline_id: str


def _check_banned_keys(raw: dict) -> None:
    """
    Assert that the raw metadata dict contains no banned keys.

    Checked recursively one level deep (top-level keys only, since
    the pipeline driver is responsible for never producing nested
    pixel payloads).
    """
    found = BANNED_METADATA_KEYS & raw.keys()
    if found:
        raise PrivacyViolationError(
            f"Privacy contract violation: raw pipeline metadata contains "
            f"banned key(s): {sorted(found)}. No observation will be published."
        )


def build_observation(raw_meta: dict, context: ObservationContext) -> CvObservation:
    """
    Map a raw pipeline metadata dict into a typed CvObservation.

    Args:
        raw_meta: dict from PipelineDriver.read_metadata() — must not
                  contain banned keys. Expected keys: frame_seq (int),
                  person_count (int), confidence_mean (float).
        context: deployment identity fields.

    Returns:
        CvObservation ready for serialization and publishing.

    Raises:
        PrivacyViolationError: if raw_meta contains any banned key.
    """
    _check_banned_keys(raw_meta)

    counts = ObservationCounts(
        persons=int(raw_meta.get("person_count", 0)),
        confidence_mean=float(raw_meta.get("confidence_mean", 0.0)),
    )

    quality = {
        "pipeline_fps": raw_meta.get("pipeline_fps"),
        "inference_ms": raw_meta.get("inference_ms"),
    }

    return CvObservation(
        tenant_id=context.tenant_id,
        site_id=context.site_id,
        camera_id=context.camera_id,
        pipeline_id=context.pipeline_id,
        frame_seq=int(raw_meta.get("frame_seq", 0)),
        counts=counts,
        quality=quality,
    )
