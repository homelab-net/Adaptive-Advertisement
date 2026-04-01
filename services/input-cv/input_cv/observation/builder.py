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

from .models import BANNED_METADATA_KEYS, CvObservation, ObservationCounts, ObservationDemographics


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
                  person_count (int), confidence_mean (float),
                  frames_processed (int, default 1), frames_dropped (int, default 0),
                  pipeline_degraded (bool, optional).
        context: deployment identity fields.

    Returns:
        CvObservation ready for serialization and publishing.

    Raises:
        PrivacyViolationError: if raw_meta contains any banned key.
    """
    _check_banned_keys(raw_meta)

    counts = ObservationCounts(
        present=int(raw_meta.get("person_count", 0)),
        confidence=float(raw_meta.get("confidence_mean", 0.0)),
    )

    quality: dict = {
        "frames_processed": int(raw_meta.get("frames_processed", 1)),
        "frames_dropped": int(raw_meta.get("frames_dropped", 0)),
    }
    if "pipeline_degraded" in raw_meta:
        quality["pipeline_degraded"] = bool(raw_meta["pipeline_degraded"])

    demographics: ObservationDemographics | None = None
    if "demographics" in raw_meta:
        raw_demog = raw_meta["demographics"]
        demographics = ObservationDemographics(
            age_group=raw_demog.get("age_group"),
            gender=raw_demog.get("gender"),
            dwell_estimate_ms=raw_demog.get("dwell_estimate_ms"),
            suppressed=raw_demog.get("suppressed"),
        )

    return CvObservation(
        tenant_id=context.tenant_id,
        site_id=context.site_id,
        camera_id=context.camera_id,
        pipeline_id=context.pipeline_id,
        frame_seq=int(raw_meta.get("frame_seq", 0)),
        counts=counts,
        demographics=demographics,
        quality=quality,
    )
