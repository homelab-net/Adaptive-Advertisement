"""
Unit tests for dashboard_api.audience_sink._parse_snapshot.

Exercises the JSON → AudienceSnapshot parsing path directly, without MQTT or DB.
Covers privacy gating, demographics suppression, age_group parsing, and gender
parsing (CRM-003).
"""
from __future__ import annotations

import json

import pytest

from dashboard_api.audience_sink import _parse_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(**overrides) -> bytes:
    """Build a minimal valid ICD-3 JSON payload."""
    base: dict = {
        "schema_version": "1.0.0",
        "message_type": "audience_state_signal",
        "message_id": "sig-001",
        "produced_at": "2026-01-15T12:00:01Z",
        "tenant_id": "tenant-01",
        "site_id": "site-01",
        "camera_id": "cam-01",
        "state": {
            "presence": {"count": 2, "confidence": 0.87},
            "stability": {"state_stable": True, "freeze_decision": False},
        },
        "source_quality": {"signal_age_ms": 250, "pipeline_degraded": False},
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }
    base.update(overrides)
    return json.dumps(base).encode()


def _payload_with_demographics(
    *,
    suppressed: bool = False,
    age_group: dict | None = None,
    gender: dict | None = None,
) -> bytes:
    demog: dict = {"suppressed": suppressed}
    if age_group is not None:
        demog["age_group"] = age_group
    if gender is not None:
        demog["gender"] = gender

    msg = json.loads(_payload())
    msg["state"]["demographics"] = demog
    return json.dumps(msg).encode()


_FULL_AGE = {
    "child": 0.05,
    "young_adult": 0.35,
    "adult": 0.45,
    "senior": 0.15,
}

_FULL_GENDER = {"male": 0.70, "female": 0.30}


# ---------------------------------------------------------------------------
# Happy path — minimal payload
# ---------------------------------------------------------------------------

class TestParseSnapshotHappyPath:
    def test_minimal_valid_returns_snapshot(self):
        snap = _parse_snapshot(_payload())
        assert snap is not None

    def test_presence_count_parsed(self):
        snap = _parse_snapshot(_payload())
        assert snap.presence_count == 2

    def test_presence_confidence_parsed(self):
        snap = _parse_snapshot(_payload())
        assert snap.presence_confidence == pytest.approx(0.87)

    def test_state_stable_parsed(self):
        snap = _parse_snapshot(_payload())
        assert snap.state_stable is True

    def test_pipeline_degraded_false_parsed(self):
        snap = _parse_snapshot(_payload())
        assert snap.pipeline_degraded is False

    def test_pipeline_degraded_true_parsed(self):
        msg = json.loads(_payload())
        msg["source_quality"]["pipeline_degraded"] = True
        snap = _parse_snapshot(json.dumps(msg).encode())
        assert snap.pipeline_degraded is True


# ---------------------------------------------------------------------------
# Privacy gate
# ---------------------------------------------------------------------------

class TestPrivacyGate:
    def test_contains_images_true_returns_none(self):
        msg = json.loads(_payload())
        msg["privacy"]["contains_images"] = True
        assert _parse_snapshot(json.dumps(msg).encode()) is None

    def test_contains_frame_urls_true_returns_none(self):
        msg = json.loads(_payload())
        msg["privacy"]["contains_frame_urls"] = True
        assert _parse_snapshot(json.dumps(msg).encode()) is None

    def test_contains_face_embeddings_true_returns_none(self):
        msg = json.loads(_payload())
        msg["privacy"]["contains_face_embeddings"] = True
        assert _parse_snapshot(json.dumps(msg).encode()) is None

    def test_invalid_json_returns_none(self):
        assert _parse_snapshot(b"not json") is None

    def test_missing_state_returns_none(self):
        msg = json.loads(_payload())
        del msg["state"]
        assert _parse_snapshot(json.dumps(msg).encode()) is None


# ---------------------------------------------------------------------------
# Demographics suppression
# ---------------------------------------------------------------------------

class TestDemographicsSuppression:
    def test_no_demographics_block_suppressed_defaults_true(self):
        snap = _parse_snapshot(_payload())
        # When demographics block is absent, suppressed defaults True
        assert snap.demographics_suppressed is True
        assert snap.age_group_adult is None
        assert snap.age_group_child is None

    def test_suppressed_true_writes_null_columns(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=True,
            age_group=_FULL_AGE,
            gender=_FULL_GENDER,
        ))
        assert snap is not None
        assert snap.demographics_suppressed is True
        assert snap.age_group_adult is None
        assert snap.age_group_child is None
        assert snap.gender_male is None
        assert snap.gender_female is None

    def test_suppressed_false_writes_age_columns(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=False,
            age_group=_FULL_AGE,
        ))
        assert snap is not None
        assert snap.demographics_suppressed is False
        assert snap.age_group_adult == pytest.approx(0.45)
        assert snap.age_group_child == pytest.approx(0.05)
        assert snap.age_group_young_adult == pytest.approx(0.35)
        assert snap.age_group_senior == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Gender parsing (CRM-003)
# ---------------------------------------------------------------------------

class TestGenderParsing:
    def test_gender_bins_parsed_when_not_suppressed(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=False,
            age_group=_FULL_AGE,
            gender=_FULL_GENDER,
        ))
        assert snap is not None
        assert snap.gender_male == pytest.approx(0.70)
        assert snap.gender_female == pytest.approx(0.30)

    def test_gender_absent_writes_none(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=False,
            age_group=_FULL_AGE,
            # no gender key
        ))
        assert snap is not None
        assert snap.gender_male is None
        assert snap.gender_female is None

    def test_gender_suppressed_writes_none(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=True,
            age_group=_FULL_AGE,
            gender=_FULL_GENDER,
        ))
        assert snap is not None
        assert snap.gender_male is None
        assert snap.gender_female is None

    def test_gender_without_age_group(self):
        """Gender can appear without age_group (partial demographic support)."""
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=False,
            gender=_FULL_GENDER,
        ))
        assert snap is not None
        assert snap.gender_male == pytest.approx(0.70)
        assert snap.gender_female == pytest.approx(0.30)
        assert snap.age_group_adult is None

    def test_gender_male_only_female_none(self):
        snap = _parse_snapshot(_payload_with_demographics(
            suppressed=False,
            gender={"male": 1.0},
        ))
        assert snap is not None
        assert snap.gender_male == pytest.approx(1.0)
        assert snap.gender_female is None
