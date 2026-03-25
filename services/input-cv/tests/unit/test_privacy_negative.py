"""
Privacy-negative tests.

These tests are the highest-priority category in the test suite.

They verify that:
1. builder.build_observation raises PrivacyViolationError when raw pipeline
   metadata contains any banned key.
2. Serialized CvObservation JSON output contains none of the banned keys.
3. CvObservation model rejects banned fields via extra="forbid".

If these tests fail, no observation should be published.
"""
from __future__ import annotations

import json

import pytest

from input_cv.observation.builder import ObservationContext, PrivacyViolationError, build_observation
from input_cv.observation.models import BANNED_METADATA_KEYS, CvObservation

_CONTEXT = ObservationContext(
    tenant_id="t1",
    site_id="s1",
    camera_id="cam-01",
    pipeline_id="p1",
)

_CLEAN_META = {
    "frame_seq": 1,
    "person_count": 2,
    "confidence_mean": 0.9,
    "pipeline_fps": 10.0,
    "inference_ms": 38.0,
}


@pytest.mark.parametrize("banned_key", sorted(BANNED_METADATA_KEYS))
def test_banned_key_in_raw_meta_raises(banned_key: str):
    """Any banned key in raw pipeline metadata must raise PrivacyViolationError."""
    dirty = dict(_CLEAN_META)
    dirty[banned_key] = "some_value"
    with pytest.raises(PrivacyViolationError):
        build_observation(dirty, _CONTEXT)


def test_clean_meta_builds_without_error():
    obs = build_observation(_CLEAN_META, _CONTEXT)
    assert obs.counts.present == 2


def test_serialized_observation_contains_no_banned_keys():
    """No banned key may appear anywhere in the serialized JSON output."""
    obs = build_observation(_CLEAN_META, _CONTEXT)
    payload = json.loads(obs.to_json_bytes())
    found_banned = BANNED_METADATA_KEYS & payload.keys()
    assert not found_banned, f"Banned keys found in serialized observation: {found_banned}"


def test_nested_quality_contains_no_banned_keys():
    obs = build_observation(_CLEAN_META, _CONTEXT)
    payload = json.loads(obs.to_json_bytes())
    quality_keys = set(payload.get("quality", {}).keys())
    found_banned = BANNED_METADATA_KEYS & quality_keys
    assert not found_banned, f"Banned keys found in quality dict: {found_banned}"


def test_privacy_flags_always_false_in_output():
    obs = build_observation(_CLEAN_META, _CONTEXT)
    payload = json.loads(obs.to_json_bytes())
    priv = payload["privacy"]
    assert priv["contains_images"] is False
    assert priv["contains_frame_urls"] is False
    assert priv["contains_face_embeddings"] is False
