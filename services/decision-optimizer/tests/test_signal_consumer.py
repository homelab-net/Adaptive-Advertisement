"""
Unit tests for SignalConsumer — ICD-3 signal ingestion and validation.
"""
import json
import time
import pytest

from decision_optimizer.signal_consumer import SignalConsumer
from tests.conftest import make_signal


@pytest.fixture()
def consumer() -> SignalConsumer:
    return SignalConsumer()


def raw(signal: dict) -> bytes:
    return json.dumps(signal).encode()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidSignals:
    def test_valid_signal_accepted(self, consumer):
        accepted = consumer.process(raw(make_signal()))
        assert accepted is True

    def test_latest_signal_set_after_accept(self, consumer):
        consumer.process(raw(make_signal(message_id="x")))
        assert consumer.latest_signal is not None
        assert consumer.latest_signal["message_id"] == "x"

    def test_signal_age_ms_tracks_time(self, consumer):
        assert consumer.signal_age_ms() is None  # no signal yet
        consumer.process(raw(make_signal()))
        age = consumer.signal_age_ms()
        assert age is not None
        assert 0 <= age < 500  # should be near-zero

    def test_accepts_string_payload(self, consumer):
        accepted = consumer.process(json.dumps(make_signal()))
        assert accepted is True

    def test_status_reports_totals(self, consumer):
        consumer.process(raw(make_signal(message_id="a")))
        consumer.process(raw(make_signal(message_id="b")))
        s = consumer.status()
        assert s["total_received"] == 2
        assert s["total_rejected"] == 0


# ---------------------------------------------------------------------------
# Rejection cases
# ---------------------------------------------------------------------------

class TestRejection:
    def test_invalid_json_rejected(self, consumer):
        assert consumer.process(b"not json {{{") is False
        assert consumer.latest_signal is None

    def test_missing_required_fields_rejected(self, consumer):
        bad = {"schema_version": "1.0.0", "message_type": "audience_state_signal"}
        assert consumer.process(raw(bad)) is False

    def test_wrong_schema_version_rejected(self, consumer):
        bad = make_signal()
        bad["schema_version"] = "9.9.9"
        assert consumer.process(raw(bad)) is False

    def test_privacy_violation_rejected(self, consumer):
        """contains_images must be false (schema const) — violation must be caught."""
        bad = make_signal()
        bad["privacy"]["contains_images"] = True
        assert consumer.process(raw(bad)) is False

    def test_frame_url_violation_rejected(self, consumer):
        bad = make_signal()
        bad["privacy"]["contains_frame_urls"] = True
        assert consumer.process(raw(bad)) is False

    def test_face_embedding_violation_rejected(self, consumer):
        bad = make_signal()
        bad["privacy"]["contains_face_embeddings"] = True
        assert consumer.process(raw(bad)) is False

    def test_rejected_count_tracked(self, consumer):
        consumer.process(b"invalid json")
        assert consumer.status()["total_rejected"] == 1


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_message_id_deduplicated(self, consumer):
        s = make_signal(message_id="dup-1")
        assert consumer.process(raw(s)) is True
        assert consumer.process(raw(s)) is False

    def test_different_ids_both_accepted(self, consumer):
        assert consumer.process(raw(make_signal(message_id="a"))) is True
        assert consumer.process(raw(make_signal(message_id="b"))) is True
        assert consumer.status()["total_received"] == 2

    def test_latest_updated_on_new_message(self, consumer):
        consumer.process(raw(make_signal(message_id="first", count=1)))
        consumer.process(raw(make_signal(message_id="second", count=5)))
        assert consumer.latest_signal["state"]["presence"]["count"] == 5

    def test_latest_not_overwritten_by_duplicate(self, consumer):
        consumer.process(raw(make_signal(message_id="x", count=1)))
        # Manually mutate the stored signal to confirm it's the same object
        original_id = id(consumer.latest_signal)
        consumer.process(raw(make_signal(message_id="x", count=99)))
        # Still the same object (not overwritten)
        assert id(consumer.latest_signal) == original_id


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_signal_age_before_any_received(self, consumer):
        assert consumer.signal_age_ms() is None

    def test_latest_signal_none_before_any_received(self, consumer):
        assert consumer.latest_signal is None

    def test_status_latest_message_id_none_before_any(self, consumer):
        assert consumer.status()["latest_message_id"] is None
