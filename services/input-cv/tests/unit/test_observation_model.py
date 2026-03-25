"""CvObservation model — structure and serialization tests."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from input_cv.observation.models import (
    BANNED_METADATA_KEYS,
    CvObservation,
    ObservationCounts,
    ObservationPrivacy,
)


def test_observation_default_privacy_flags():
    priv = ObservationPrivacy()
    assert priv.contains_images is False
    assert priv.contains_frame_urls is False
    assert priv.contains_face_embeddings is False


def test_observation_privacy_rejects_true_contains_images():
    with pytest.raises(ValidationError):
        ObservationPrivacy(contains_images=True)


def test_observation_privacy_rejects_true_contains_frame_urls():
    with pytest.raises(ValidationError):
        ObservationPrivacy(contains_frame_urls=True)


def test_observation_privacy_rejects_true_contains_face_embeddings():
    with pytest.raises(ValidationError):
        ObservationPrivacy(contains_face_embeddings=True)


def test_observation_serializes_to_json():
    obs = CvObservation(
        tenant_id="t1",
        site_id="s1",
        camera_id="cam-01",
        pipeline_id="p1",
        frame_seq=42,
    )
    payload = json.loads(obs.to_json_bytes())
    assert payload["tenant_id"] == "t1"
    assert payload["frame_seq"] == 42
    assert payload["message_type"] == "cv_observation"
    assert "message_id" in payload
    assert "produced_at" in payload


def test_observation_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        CvObservation(
            tenant_id="t1",
            site_id="s1",
            camera_id="cam-01",
            pipeline_id="p1",
            frame_seq=0,
            raw_frame=b"data",  # banned extra field
        )


def test_counts_present_non_negative():
    with pytest.raises(ValidationError):
        ObservationCounts(present=-1)


def test_banned_metadata_keys_is_nonempty():
    assert len(BANNED_METADATA_KEYS) > 0
    assert "frame" in BANNED_METADATA_KEYS
    assert "embedding" in BANNED_METADATA_KEYS
    assert "base64" in BANNED_METADATA_KEYS
