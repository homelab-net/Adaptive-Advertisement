"""
ICD-3 contract tests — AudienceStateSignal (audience-state → decision-optimizer, MQTT).

Schema: contracts/decision-optimizer/audience-state-signal.schema.json  v1.0

The smoothing layer must not introduce image data that ICD-2 forbids.
Privacy invariants are re-verified here as a downstream check.
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("decision-optimizer/audience-state-signal.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid() -> dict:
    return {
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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidSignal:
    def test_minimal_valid_payload(self, valid):
        assert_valid(SCHEMA, valid)

    def test_with_demographics(self, valid):
        valid["state"]["demographics"] = {
            "age_group": {
                "child": 0.05,
                "young_adult": 0.40,
                "adult": 0.45,
                "senior": 0.10,
            },
            "dwell_estimate_ms": 2800,
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_demographics_suppressed(self, valid):
        valid["state"]["demographics"] = {"suppressed": True}
        assert_valid(SCHEMA, valid)

    def test_freeze_decision_true(self, valid):
        valid["state"]["stability"]["freeze_decision"] = True
        assert_valid(SCHEMA, valid)

    def test_state_not_stable(self, valid):
        valid["state"]["stability"]["state_stable"] = False
        assert_valid(SCHEMA, valid)

    def test_observations_in_window_optional(self, valid):
        valid["state"]["stability"]["observations_in_window"] = 5
        assert_valid(SCHEMA, valid)

    def test_observations_dropped_optional(self, valid):
        valid["source_quality"]["observations_dropped"] = 2
        assert_valid(SCHEMA, valid)

    def test_zero_presence(self, valid):
        valid["state"]["presence"]["count"] = 0
        valid["state"]["presence"]["confidence"] = 0.0
        assert_valid(SCHEMA, valid)

    def test_high_signal_age(self, valid):
        valid["source_quality"]["signal_age_ms"] = 30000
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "message_type", "message_id", "produced_at",
        "tenant_id", "site_id", "camera_id", "state", "source_quality", "privacy",
    ])
    def test_missing_top_level_required(self, valid, field):
        del valid[field]
        assert_invalid(SCHEMA, valid)

    def test_missing_state_presence_rejected(self, valid):
        del valid["state"]["presence"]
        assert_invalid(SCHEMA, valid)

    def test_missing_state_stability_rejected(self, valid):
        del valid["state"]["stability"]
        assert_invalid(SCHEMA, valid)

    def test_missing_presence_count_rejected(self, valid):
        del valid["state"]["presence"]["count"]
        assert_invalid(SCHEMA, valid)

    def test_missing_presence_confidence_rejected(self, valid):
        del valid["state"]["presence"]["confidence"]
        assert_invalid(SCHEMA, valid)

    def test_missing_stability_state_stable_rejected(self, valid):
        del valid["state"]["stability"]["state_stable"]
        assert_invalid(SCHEMA, valid)

    def test_missing_stability_freeze_decision_rejected(self, valid):
        del valid["state"]["stability"]["freeze_decision"]
        assert_invalid(SCHEMA, valid)

    def test_missing_source_quality_signal_age_ms_rejected(self, valid):
        del valid["source_quality"]["signal_age_ms"]
        assert_invalid(SCHEMA, valid)

    def test_missing_source_quality_pipeline_degraded_rejected(self, valid):
        del valid["source_quality"]["pipeline_degraded"]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Privacy invariants — downstream mirror of ICD-2
# ---------------------------------------------------------------------------

class TestPrivacyInvariants:
    def test_contains_images_true_rejected(self, valid):
        valid["privacy"]["contains_images"] = True
        assert_invalid(SCHEMA, valid)

    def test_contains_frame_urls_true_rejected(self, valid):
        valid["privacy"]["contains_frame_urls"] = True
        assert_invalid(SCHEMA, valid)

    def test_contains_face_embeddings_true_rejected(self, valid):
        valid["privacy"]["contains_face_embeddings"] = True
        assert_invalid(SCHEMA, valid)

    @pytest.mark.parametrize("flag", [
        "contains_images", "contains_frame_urls", "contains_face_embeddings",
    ])
    def test_missing_privacy_flag_rejected(self, valid, flag):
        del valid["privacy"][flag]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Const / enum enforcement
# ---------------------------------------------------------------------------

class TestConstFields:
    def test_wrong_schema_version_rejected(self, valid):
        valid["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, valid)

    def test_wrong_message_type_rejected(self, valid):
        valid["message_type"] = "cv_observation"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

class TestNumericBounds:
    def test_confidence_above_1_rejected(self, valid):
        valid["state"]["presence"]["confidence"] = 1.01
        assert_invalid(SCHEMA, valid)

    def test_confidence_below_0_rejected(self, valid):
        valid["state"]["presence"]["confidence"] = -0.01
        assert_invalid(SCHEMA, valid)

    def test_signal_age_negative_rejected(self, valid):
        valid["source_quality"]["signal_age_ms"] = -1
        assert_invalid(SCHEMA, valid)

    def test_presence_count_negative_rejected(self, valid):
        valid["state"]["presence"]["count"] = -1
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_top_level_rejected(self, valid):
        valid["raw_embedding"] = [0.1, 0.2]
        assert_invalid(SCHEMA, valid)

    def test_unknown_state_field_rejected(self, valid):
        valid["state"]["identity_vector"] = "abc"
        assert_invalid(SCHEMA, valid)

    def test_unknown_privacy_field_rejected(self, valid):
        valid["privacy"]["contains_voice_print"] = False
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Gender demographic bins (CRM-003)
# ---------------------------------------------------------------------------

class TestGenderDemographics:
    def test_with_gender_bins_valid(self, valid):
        valid["state"]["demographics"] = {
            "gender": {"male": 0.72, "female": 0.28},
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_gender_alongside_age_group_valid(self, valid):
        valid["state"]["demographics"] = {
            "age_group": {
                "child": 0.0,
                "young_adult": 0.25,
                "adult": 0.55,
                "senior": 0.20,
            },
            "gender": {"male": 0.60, "female": 0.40},
            "dwell_estimate_ms": 3500,
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_gender_bin_below_minimum_rejected(self, valid):
        valid["state"]["demographics"] = {
            "gender": {"male": -0.01, "female": 1.0},
        }
        assert_invalid(SCHEMA, valid)

    def test_gender_bin_above_maximum_rejected(self, valid):
        valid["state"]["demographics"] = {
            "gender": {"male": 1.01, "female": 0.0},
        }
        assert_invalid(SCHEMA, valid)

    def test_unknown_gender_bin_rejected(self, valid):
        valid["state"]["demographics"] = {
            "gender": {"male": 0.5, "female": 0.4, "non_binary": 0.1},
        }
        assert_invalid(SCHEMA, valid)
