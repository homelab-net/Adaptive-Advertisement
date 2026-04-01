"""
ICD-2 contract tests — CvObservation (input-cv → audience-state, MQTT).

Schema: contracts/audience-state/cv-observation.schema.json  v1.0

Privacy invariants tested here are load-bearing — any failure means
raw image data could flow through the pipeline.
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("audience-state/cv-observation.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid() -> dict:
    return {
        "schema_version": "1.0.0",
        "message_type": "cv_observation",
        "message_id": "obs-001",
        "produced_at": "2026-01-15T12:00:00Z",
        "tenant_id": "tenant-01",
        "site_id": "site-01",
        "camera_id": "cam-01",
        "pipeline_id": "pipeline-01",
        "frame_seq": 100,
        "window_ms": 500,
        "counts": {"present": 2, "confidence": 0.92},
        "quality": {"frames_processed": 15, "frames_dropped": 0},
        "privacy": {
            "contains_images": False,
            "contains_frame_urls": False,
            "contains_face_embeddings": False,
        },
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidObservation:
    def test_minimal_valid_payload(self, valid):
        assert_valid(SCHEMA, valid)

    def test_with_full_demographics(self, valid):
        valid["demographics"] = {
            "age_group": {
                "child": 0.05,
                "young_adult": 0.40,
                "adult": 0.45,
                "senior": 0.10,
            },
            "dwell_estimate_ms": 3200,
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_with_pipeline_degraded_flag(self, valid):
        valid["quality"]["pipeline_degraded"] = True
        assert_valid(SCHEMA, valid)

    def test_zero_persons_present(self, valid):
        valid["counts"]["present"] = 0
        valid["counts"]["confidence"] = 0.0
        assert_valid(SCHEMA, valid)

    def test_confidence_boundaries(self, valid):
        for c in (0.0, 0.5, 1.0):
            valid["counts"]["confidence"] = c
            assert_valid(SCHEMA, valid)

    def test_frame_seq_zero(self, valid):
        valid["frame_seq"] = 0
        assert_valid(SCHEMA, valid)

    def test_window_ms_boundaries(self, valid):
        valid["window_ms"] = 1
        assert_valid(SCHEMA, valid)
        valid["window_ms"] = 60000
        assert_valid(SCHEMA, valid)

    def test_demographics_suppressed(self, valid):
        valid["demographics"] = {"suppressed": True}
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "message_type", "message_id", "produced_at",
        "tenant_id", "site_id", "camera_id", "pipeline_id",
        "frame_seq", "window_ms", "counts", "quality", "privacy",
    ])
    def test_missing_required_field_rejected(self, valid, field):
        del valid[field]
        assert_invalid(SCHEMA, valid)

    def test_missing_counts_present_rejected(self, valid):
        del valid["counts"]["present"]
        assert_invalid(SCHEMA, valid)

    def test_missing_counts_confidence_rejected(self, valid):
        del valid["counts"]["confidence"]
        assert_invalid(SCHEMA, valid)

    def test_missing_quality_frames_processed_rejected(self, valid):
        del valid["quality"]["frames_processed"]
        assert_invalid(SCHEMA, valid)

    def test_missing_quality_frames_dropped_rejected(self, valid):
        del valid["quality"]["frames_dropped"]
        assert_invalid(SCHEMA, valid)

    @pytest.mark.parametrize("flag", [
        "contains_images", "contains_frame_urls", "contains_face_embeddings",
    ])
    def test_missing_privacy_flag_rejected(self, valid, flag):
        del valid["privacy"][flag]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Privacy invariants — const:false enforcement
# These are the highest-priority tests. A passing privacy flag must never
# be allowed to be True.
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

    def test_all_privacy_flags_false_required(self, valid):
        # All three must be false — any true value is rejected
        for flag in ("contains_images", "contains_frame_urls", "contains_face_embeddings"):
            bad = dict(valid)
            bad["privacy"] = dict(valid["privacy"])
            bad["privacy"][flag] = True
            assert_invalid(SCHEMA, bad), f"privacy.{flag}=True should be rejected"


# ---------------------------------------------------------------------------
# schema_version and message_type enforcement
# ---------------------------------------------------------------------------

class TestConstFields:
    def test_wrong_schema_version_rejected(self, valid):
        valid["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, valid)

    def test_wrong_message_type_rejected(self, valid):
        valid["message_type"] = "audience_state_signal"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

class TestNumericBounds:
    def test_confidence_above_1_rejected(self, valid):
        valid["counts"]["confidence"] = 1.01
        assert_invalid(SCHEMA, valid)

    def test_confidence_below_0_rejected(self, valid):
        valid["counts"]["confidence"] = -0.01
        assert_invalid(SCHEMA, valid)

    def test_window_ms_zero_rejected(self, valid):
        valid["window_ms"] = 0
        assert_invalid(SCHEMA, valid)

    def test_window_ms_above_max_rejected(self, valid):
        valid["window_ms"] = 60001
        assert_invalid(SCHEMA, valid)

    def test_frame_seq_negative_rejected(self, valid):
        valid["frame_seq"] = -1
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_top_level_field_rejected(self, valid):
        valid["raw_frame"] = "data:image/jpeg;base64,..."
        assert_invalid(SCHEMA, valid)

    def test_unknown_counts_field_rejected(self, valid):
        valid["counts"]["per_person_ids"] = ["id-1", "id-2"]
        assert_invalid(SCHEMA, valid)

    def test_unknown_privacy_field_rejected(self, valid):
        valid["privacy"]["contains_biometric_template"] = False
        assert_invalid(SCHEMA, valid)

    def test_unknown_demographics_field_rejected(self, valid):
        valid["demographics"] = {"face_id": "abc123"}
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Gender demographic bins (CRM-003)
# ---------------------------------------------------------------------------

class TestGenderDemographics:
    def test_with_gender_bins_valid(self, valid):
        valid["demographics"] = {
            "gender": {"male": 0.70, "female": 0.30},
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_gender_alongside_age_group_valid(self, valid):
        valid["demographics"] = {
            "age_group": {
                "child": 0.0,
                "young_adult": 0.30,
                "adult": 0.50,
                "senior": 0.20,
            },
            "gender": {"male": 0.65, "female": 0.35},
            "dwell_estimate_ms": 4100,
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_gender_bins_at_boundaries(self, valid):
        valid["demographics"] = {
            "gender": {"male": 0.0, "female": 1.0},
            "suppressed": False,
        }
        assert_valid(SCHEMA, valid)

    def test_gender_bin_below_minimum_rejected(self, valid):
        valid["demographics"] = {
            "gender": {"male": -0.1, "female": 1.0},
        }
        assert_invalid(SCHEMA, valid)

    def test_gender_bin_above_maximum_rejected(self, valid):
        valid["demographics"] = {
            "gender": {"male": 1.1, "female": 0.0},
        }
        assert_invalid(SCHEMA, valid)

    def test_unknown_gender_bin_rejected(self, valid):
        valid["demographics"] = {
            "gender": {"male": 0.5, "female": 0.4, "unknown_bin": 0.1},
        }
        assert_invalid(SCHEMA, valid)
