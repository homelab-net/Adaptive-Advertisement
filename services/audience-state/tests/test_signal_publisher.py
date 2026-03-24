"""
Unit tests for SignalPublisher — ICD-3 signal construction and validation.
Tests build_signal() only (no MQTT client needed).
"""
import json
import pytest

import jsonschema
from pathlib import Path

from audience_state.observation_store import ObservationWindow
from audience_state.signal_publisher import SignalPublisher
from tests.conftest import make_observation


_ICD3_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "contracts" / "decision-optimizer" / "audience-state-signal.schema.json"
)


@pytest.fixture()
def icd3_validator():
    with open(_ICD3_SCHEMA_PATH) as f:
        schema = json.load(f)
    return jsonschema.Draft202012Validator(schema)


def make_window_with_obs(
    count: int = 1,
    confidence: float = 0.9,
    pipeline_degraded: bool = False,
    min_stability: int = 1,
    n_obs: int = 1,
) -> ObservationWindow:
    w = ObservationWindow(
        window_ms=5000,
        min_stability_observations=min_stability,
        confidence_freeze_threshold=0.5,
    )
    for i in range(n_obs):
        w.add(make_observation(
            count=count,
            confidence=confidence,
            pipeline_degraded=pipeline_degraded,
            message_id=f"obs-{i}",
        ))
    return w


# ---------------------------------------------------------------------------
# Empty window
# ---------------------------------------------------------------------------

def test_build_signal_empty_window_returns_none():
    pub = SignalPublisher()
    w = ObservationWindow(window_ms=5000, min_stability_observations=1, confidence_freeze_threshold=0.5)
    assert pub.build_signal(w) is None


# ---------------------------------------------------------------------------
# Signal structure
# ---------------------------------------------------------------------------

class TestSignalStructure:
    def test_returns_dict(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert isinstance(sig, dict)

    def test_schema_version(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert sig["schema_version"] == "1.0.0"

    def test_message_type(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert sig["message_type"] == "audience_state_signal"

    def test_message_id_is_uuid(self):
        import uuid
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        uuid.UUID(sig["message_id"])  # raises if not valid UUID

    def test_message_id_unique_per_call(self):
        pub = SignalPublisher()
        w = make_window_with_obs(n_obs=3)
        ids = {pub.build_signal(w)["message_id"] for _ in range(5)}
        assert len(ids) == 5  # all unique

    def test_produced_at_iso8601(self):
        from datetime import datetime, timezone
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        # Should parse without error
        datetime.fromisoformat(sig["produced_at"].replace("Z", "+00:00"))

    def test_presence_count_and_confidence(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(count=3, confidence=0.85))
        assert sig["state"]["presence"]["count"] == 3
        assert sig["state"]["presence"]["confidence"] == pytest.approx(0.85, abs=0.01)

    def test_source_quality_fields_present(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        sq = sig["source_quality"]
        assert "signal_age_ms" in sq
        assert "pipeline_degraded" in sq

    def test_source_quality_pipeline_degraded_propagates(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(pipeline_degraded=True))
        assert sig["source_quality"]["pipeline_degraded"] is True

    def test_source_quality_clean_pipeline(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(pipeline_degraded=False))
        assert sig["source_quality"]["pipeline_degraded"] is False


# ---------------------------------------------------------------------------
# Privacy hard contract
# ---------------------------------------------------------------------------

class TestPrivacyBlock:
    def test_contains_images_always_false(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert sig["privacy"]["contains_images"] is False

    def test_contains_frame_urls_always_false(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert sig["privacy"]["contains_frame_urls"] is False

    def test_contains_face_embeddings_always_false(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs())
        assert sig["privacy"]["contains_face_embeddings"] is False


# ---------------------------------------------------------------------------
# Schema conformance (end-to-end ICD-3 validation)
# ---------------------------------------------------------------------------

class TestSchemaConformance:
    def test_signal_passes_icd3_schema(self, icd3_validator):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(n_obs=3, min_stability=3))
        errors = list(icd3_validator.iter_errors(sig))
        assert errors == [], f"ICD-3 schema violations: {[e.message for e in errors]}"

    def test_signal_with_freeze_passes_schema(self, icd3_validator):
        pub = SignalPublisher()
        sig = pub.build_signal(
            make_window_with_obs(confidence=0.3)  # below threshold → freeze
        )
        errors = list(icd3_validator.iter_errors(sig))
        assert errors == []

    def test_signal_with_degraded_pipeline_passes_schema(self, icd3_validator):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(pipeline_degraded=True))
        errors = list(icd3_validator.iter_errors(sig))
        assert errors == []


# ---------------------------------------------------------------------------
# Stability flags in published signal
# ---------------------------------------------------------------------------

class TestStabilityInSignal:
    def test_not_stable_when_below_min_obs(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(n_obs=1, min_stability=3))
        assert sig["state"]["stability"]["state_stable"] is False
        assert sig["state"]["stability"]["freeze_decision"] is True

    def test_stable_when_enough_obs(self):
        pub = SignalPublisher()
        sig = pub.build_signal(make_window_with_obs(
            n_obs=3, min_stability=3, confidence=0.9
        ))
        assert sig["state"]["stability"]["state_stable"] is True
        assert sig["state"]["stability"]["freeze_decision"] is False


# ---------------------------------------------------------------------------
# Validation failure counter
# ---------------------------------------------------------------------------

def test_validation_failure_does_not_increment_on_valid(monkeypatch):
    pub = SignalPublisher()
    pub.build_signal(make_window_with_obs())
    assert pub.status()["validation_failures"] == 0
