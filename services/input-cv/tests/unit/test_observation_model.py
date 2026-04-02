"""CvObservation model — structure and serialization tests."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from input_cv.observation.models import (
    BANNED_METADATA_KEYS,
    CvObservation,
    ObservationCounts,
    ObservationDemographics,
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


# ---------------------------------------------------------------------------
# ObservationDemographics — gender field (CRM-003)
# ---------------------------------------------------------------------------

def test_demographics_gender_accepted():
    d = ObservationDemographics(
        age_group={"child": 0.0, "young_adult": 0.3, "adult": 0.5, "senior": 0.2},
        gender={"male": 0.65, "female": 0.35},
        dwell_estimate_ms=3000,
        suppressed=False,
    )
    assert d.gender == {"male": 0.65, "female": 0.35}


def test_demographics_gender_optional_none_by_default():
    d = ObservationDemographics()
    assert d.gender is None


def test_demographics_gender_dict_accepts_float_values():
    # gender is a dict[str, float] at model level; bin key enforcement is at schema level
    d = ObservationDemographics(gender={"male": 0.6, "female": 0.4})
    assert d.gender is not None
    assert d.gender["male"] == pytest.approx(0.6)


def test_observation_with_demographics_serializes_gender():
    obs = CvObservation(
        tenant_id="t1",
        site_id="s1",
        camera_id="cam-01",
        pipeline_id="p1",
        frame_seq=1,
        demographics=ObservationDemographics(
            gender={"male": 0.7, "female": 0.3},
            suppressed=False,
        ),
    )
    import json
    payload = json.loads(obs.to_json_bytes())
    assert payload["demographics"]["gender"] == {"male": 0.7, "female": 0.3}


# ---------------------------------------------------------------------------
# ObservationDemographics — attire field (CRM-005)
# ---------------------------------------------------------------------------

def test_demographics_attire_accepted():
    attire = {b: 0.1 for b in [
        "formal", "business_casual", "casual", "athletic",
        "outdoor_technical", "workwear_uniform", "streetwear",
        "luxury_premium", "lounge_comfort", "smart_occasion",
    ]}
    d = ObservationDemographics(attire=attire, suppressed=False)
    assert d.attire == attire


def test_demographics_attire_optional_none_by_default():
    d = ObservationDemographics()
    assert d.attire is None


def test_observation_with_attire_serializes():
    import json
    from input_cv.observation.models import ObservationAttention
    obs = CvObservation(
        tenant_id="t1", site_id="s1", camera_id="cam-01", pipeline_id="p1",
        frame_seq=2,
        demographics=ObservationDemographics(
            attire={"athletic": 0.6, "casual": 0.4},
            suppressed=False,
        ),
    )
    payload = json.loads(obs.to_json_bytes())
    assert payload["demographics"]["attire"]["athletic"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# ObservationAttention (CRM-004)
# ---------------------------------------------------------------------------

def test_attention_model_defaults_none():
    from input_cv.observation.models import ObservationAttention
    a = ObservationAttention()
    assert a.engaged is None
    assert a.ambient is None


def test_attention_model_accepts_valid_values():
    from input_cv.observation.models import ObservationAttention
    a = ObservationAttention(engaged=0.7, ambient=0.3)
    assert a.engaged == pytest.approx(0.7)
    assert a.ambient == pytest.approx(0.3)


def test_attention_model_rejects_out_of_range():
    from input_cv.observation.models import ObservationAttention
    with pytest.raises(ValidationError):
        ObservationAttention(engaged=1.5)


def test_observation_with_attention_serializes():
    import json
    from input_cv.observation.models import ObservationAttention
    obs = CvObservation(
        tenant_id="t1", site_id="s1", camera_id="cam-01", pipeline_id="p1",
        frame_seq=3,
        attention=ObservationAttention(engaged=0.8, ambient=0.2),
    )
    payload = json.loads(obs.to_json_bytes())
    assert payload["attention"]["engaged"] == pytest.approx(0.8)
    assert payload["attention"]["ambient"] == pytest.approx(0.2)


def test_observation_attention_none_by_default():
    obs = CvObservation(
        tenant_id="t1", site_id="s1", camera_id="cam-01", pipeline_id="p1",
        frame_seq=0,
    )
    assert obs.attention is None
