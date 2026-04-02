"""
Unit tests for dashboard_api.play_event_sink._parse_play_event.

Exercises the JSON → PlayEvent parsing path directly, without MQTT or DB.
The attention_at_trigger lookup requires an async DB session and is tested
via integration fixtures; here we focus on the parsing logic.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from dashboard_api.play_event_sink import _parse_play_event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(**overrides) -> bytes:
    base: dict = {
        "manifest_id": "manifest-abc",
        "activated_at": "2026-04-02T10:00:00Z",
        "reason": "policy_match",
        "prev_manifest_id": "manifest-xyz",
    }
    base.update(overrides)
    return json.dumps(base).encode()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestParsePlayEventHappyPath:
    def test_minimal_returns_event(self):
        event = _parse_play_event(_payload())
        assert event is not None

    def test_manifest_id_parsed(self):
        event = _parse_play_event(_payload(manifest_id="m-test"))
        assert event.manifest_id == "m-test"

    def test_activated_at_parsed(self):
        event = _parse_play_event(_payload(activated_at="2026-04-02T12:30:00Z"))
        assert event is not None
        assert event.activated_at.hour == 12
        assert event.activated_at.tzinfo is not None

    def test_reason_parsed(self):
        event = _parse_play_event(_payload(reason="policy_match"))
        assert event.reason == "policy_match"

    def test_prev_manifest_id_parsed(self):
        event = _parse_play_event(_payload(prev_manifest_id="prev-m"))
        assert event.prev_manifest_id == "prev-m"

    def test_reason_none_when_absent(self):
        event = _parse_play_event(_payload(reason=None))
        assert event.reason is None

    def test_prev_manifest_id_none_when_absent(self):
        msg = json.loads(_payload())
        del msg["prev_manifest_id"]
        event = _parse_play_event(json.dumps(msg).encode())
        assert event is not None
        assert event.prev_manifest_id is None

    def test_attention_at_trigger_defaults_none(self):
        """attention_at_trigger is set by the DB lookup, not from the MQTT payload."""
        event = _parse_play_event(_payload())
        assert event is not None
        assert event.attention_at_trigger is None


# ---------------------------------------------------------------------------
# Parse errors
# ---------------------------------------------------------------------------

class TestParsePlayEventErrors:
    def test_invalid_json_returns_none(self):
        assert _parse_play_event(b"not json") is None

    def test_missing_manifest_id_returns_none(self):
        msg = json.loads(_payload())
        del msg["manifest_id"]
        assert _parse_play_event(json.dumps(msg).encode()) is None

    def test_missing_activated_at_returns_none(self):
        msg = json.loads(_payload())
        del msg["activated_at"]
        assert _parse_play_event(json.dumps(msg).encode()) is None

    def test_invalid_activated_at_returns_none(self):
        assert _parse_play_event(_payload(activated_at="not-a-date")) is None


# ---------------------------------------------------------------------------
# Field truncation
# ---------------------------------------------------------------------------

class TestParsePlayEventTruncation:
    def test_manifest_id_truncated_to_128(self):
        long_id = "x" * 200
        event = _parse_play_event(_payload(manifest_id=long_id))
        assert event is not None
        assert len(event.manifest_id) == 128

    def test_reason_truncated_to_256(self):
        long_reason = "r" * 300
        event = _parse_play_event(_payload(reason=long_reason))
        assert event is not None
        assert len(event.reason) == 256
