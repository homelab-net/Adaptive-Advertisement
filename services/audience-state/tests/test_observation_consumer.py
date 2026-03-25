"""
Unit tests for ObservationConsumer — ICD-2 validation and deduplication.
"""
import json
import pytest

from audience_state.observation_store import ObservationWindow
from audience_state.observation_consumer import ObservationConsumer
from tests.conftest import make_observation, raw


def make_consumer() -> tuple[ObservationConsumer, ObservationWindow]:
    window = ObservationWindow(
        window_ms=5000,
        min_stability_observations=3,
        confidence_freeze_threshold=0.5,
    )
    return ObservationConsumer(window), window


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidObservations:
    def test_valid_observation_accepted(self):
        consumer, _ = make_consumer()
        assert consumer.process(raw(make_observation())) is True

    def test_accepted_observation_enters_window(self):
        consumer, window = make_consumer()
        consumer.process(raw(make_observation()))
        assert window.observation_count() == 1

    def test_total_received_increments(self):
        consumer, _ = make_consumer()
        consumer.process(raw(make_observation(message_id="a")))
        consumer.process(raw(make_observation(message_id="b")))
        assert consumer.status()["total_received"] == 2

    def test_accepts_string_payload(self):
        consumer, _ = make_consumer()
        assert consumer.process(json.dumps(make_observation())) is True

    def test_observation_with_demographics_accepted(self):
        consumer, _ = make_consumer()
        obs = make_observation(demographics={
            "age_group": {"child": 0.1, "young_adult": 0.4, "adult": 0.4, "senior": 0.1},
            "dwell_estimate_ms": 2000,
        })
        assert consumer.process(raw(obs)) is True


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------

class TestRejection:
    def test_invalid_json_rejected(self):
        consumer, _ = make_consumer()
        assert consumer.process(b"not json {{{") is False

    def test_missing_required_fields_rejected(self):
        consumer, _ = make_consumer()
        bad = {"schema_version": "1.0.0", "message_type": "cv_observation"}
        assert consumer.process(raw(bad)) is False

    def test_wrong_schema_version_rejected(self):
        consumer, _ = make_consumer()
        bad = make_observation()
        bad["schema_version"] = "9.9.9"
        assert consumer.process(raw(bad)) is False

    def test_privacy_contains_images_rejected(self):
        consumer, _ = make_consumer()
        bad = make_observation()
        bad["privacy"]["contains_images"] = True
        assert consumer.process(raw(bad)) is False

    def test_privacy_frame_urls_rejected(self):
        consumer, _ = make_consumer()
        bad = make_observation()
        bad["privacy"]["contains_frame_urls"] = True
        assert consumer.process(raw(bad)) is False

    def test_privacy_face_embeddings_rejected(self):
        consumer, _ = make_consumer()
        bad = make_observation()
        bad["privacy"]["contains_face_embeddings"] = True
        assert consumer.process(raw(bad)) is False

    def test_rejected_observation_not_in_window(self):
        consumer, window = make_consumer()
        consumer.process(b"invalid json")
        assert window.observation_count() == 0

    def test_total_rejected_tracked(self):
        consumer, _ = make_consumer()
        consumer.process(b"bad payload 1")
        consumer.process(b"bad payload 2")
        assert consumer.status()["total_rejected"] == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_message_id_blocked(self):
        consumer, _ = make_consumer()
        obs = make_observation(message_id="dup")
        assert consumer.process(raw(obs)) is True
        assert consumer.process(raw(obs)) is False

    def test_duplicate_not_added_to_window(self):
        consumer, window = make_consumer()
        obs = make_observation(message_id="dup")
        consumer.process(raw(obs))
        consumer.process(raw(obs))
        assert window.observation_count() == 1

    def test_unique_ids_all_accepted(self):
        consumer, window = make_consumer()
        for i in range(5):
            consumer.process(raw(make_observation(message_id=f"obs-{i}")))
        assert window.observation_count() == 5


# ---------------------------------------------------------------------------
# Status observability
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_includes_window_count(self):
        consumer, _ = make_consumer()
        consumer.process(raw(make_observation(message_id="a")))
        consumer.process(raw(make_observation(message_id="b")))
        s = consumer.status()
        assert s["observations_in_window"] == 2
        assert s["total_received"] == 2
        assert s["total_rejected"] == 0
