"""
Tests for PlayerEventPublisher — ICD-9 MQTT state-transition event publishing.

Tests cover:
- No-op behaviour when no client is set (MQTT disabled or disconnected)
- Correct event shape published for each transition type
- set_client / clear_client lifecycle
- status() reporting
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from player.event_publisher import PlayerEventPublisher, _build_event


# ---------------------------------------------------------------------------
# _build_event helpers
# ---------------------------------------------------------------------------

class TestBuildEvent:
    def test_required_fields_present(self):
        evt = _build_event("manifest_activated")
        assert evt["schema_version"] == "1.0.0"
        assert "event_id" in evt
        assert "produced_at" in evt
        assert evt["event_type"] == "manifest_activated"

    def test_produced_at_utc_iso(self):
        evt = _build_event("frozen")
        # Must end with Z and contain T
        assert evt["produced_at"].endswith("Z")
        assert "T" in evt["produced_at"]

    def test_optional_manifest_id_included_when_given(self):
        evt = _build_event("manifest_activated", manifest_id="m-001")
        assert evt["manifest_id"] == "m-001"

    def test_optional_manifest_id_absent_when_none(self):
        evt = _build_event("frozen")
        assert "manifest_id" not in evt

    def test_dwell_elapsed_included_when_given(self):
        evt = _build_event("manifest_deactivated", dwell_elapsed=True)
        assert evt["dwell_elapsed"] is True

    def test_rule_rationale_included_when_given(self):
        evt = _build_event("manifest_activated", rule_rationale="young_adult")
        assert evt["rule_rationale"] == "young_adult"

    def test_unique_event_ids(self):
        ids = {_build_event("frozen")["event_id"] for _ in range(20)}
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# PlayerEventPublisher — no-op when disconnected
# ---------------------------------------------------------------------------

class TestPublisherNoClient:
    @pytest.fixture
    def publisher(self):
        return PlayerEventPublisher()

    @pytest.mark.asyncio
    async def test_manifest_activated_noop(self, publisher):
        # Must not raise; MQTT disabled silently
        await publisher.manifest_activated("m-001")

    @pytest.mark.asyncio
    async def test_frozen_noop(self, publisher):
        await publisher.frozen()

    @pytest.mark.asyncio
    async def test_safe_mode_entered_noop(self, publisher):
        await publisher.safe_mode_entered()

    @pytest.mark.asyncio
    async def test_fallback_entered_noop(self, publisher):
        await publisher.fallback_entered()

    def test_status_disconnected(self, publisher):
        s = publisher.status()
        assert s["connected"] is False
        assert s["published"] == 0
        assert s["failed"] == 0


# ---------------------------------------------------------------------------
# PlayerEventPublisher — with mock client
# ---------------------------------------------------------------------------

class TestPublisherWithClient:
    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.publish = AsyncMock()
        return client

    @pytest.fixture
    def publisher(self, mock_client):
        p = PlayerEventPublisher()
        p.set_client(mock_client)
        return p

    @pytest.mark.asyncio
    async def test_manifest_activated_publishes(self, publisher, mock_client):
        await publisher.manifest_activated("m-abc", rule_rationale="young_adult")
        mock_client.publish.assert_awaited_once()
        topic, payload = mock_client.publish.call_args.args
        import json
        data = json.loads(payload)
        assert data["event_type"] == "manifest_activated"
        assert data["manifest_id"] == "m-abc"
        assert data["rule_rationale"] == "young_adult"

    @pytest.mark.asyncio
    async def test_manifest_deactivated_publishes(self, publisher, mock_client):
        await publisher.manifest_deactivated("m-abc", dwell_elapsed=True)
        mock_client.publish.assert_awaited_once()
        _, payload = mock_client.publish.call_args.args
        import json
        data = json.loads(payload)
        assert data["event_type"] == "manifest_deactivated"
        assert data["dwell_elapsed"] is True

    @pytest.mark.asyncio
    async def test_frozen_publishes(self, publisher, mock_client):
        await publisher.frozen()
        mock_client.publish.assert_awaited_once()
        _, payload = mock_client.publish.call_args.args
        import json
        assert json.loads(payload)["event_type"] == "frozen"

    @pytest.mark.asyncio
    async def test_safe_mode_entered_publishes(self, publisher, mock_client):
        await publisher.safe_mode_entered()
        _, payload = mock_client.publish.call_args.args
        import json
        assert json.loads(payload)["event_type"] == "safe_mode_entered"

    @pytest.mark.asyncio
    async def test_safe_mode_cleared_publishes(self, publisher, mock_client):
        await publisher.safe_mode_cleared()
        _, payload = mock_client.publish.call_args.args
        import json
        assert json.loads(payload)["event_type"] == "safe_mode_cleared"

    @pytest.mark.asyncio
    async def test_fallback_entered_publishes(self, publisher, mock_client):
        await publisher.fallback_entered()
        _, payload = mock_client.publish.call_args.args
        import json
        assert json.loads(payload)["event_type"] == "fallback_entered"

    @pytest.mark.asyncio
    async def test_publish_uses_qos_1(self, publisher, mock_client):
        await publisher.manifest_activated("m-001")
        assert mock_client.publish.call_args.kwargs.get("qos") == 1

    @pytest.mark.asyncio
    async def test_status_increments_on_success(self, publisher, mock_client):
        await publisher.manifest_activated("m-001")
        await publisher.frozen()
        s = publisher.status()
        assert s["connected"] is True
        assert s["published"] == 2
        assert s["failed"] == 0

    @pytest.mark.asyncio
    async def test_status_increments_failed_on_error(self, publisher, mock_client):
        mock_client.publish.side_effect = Exception("broker down")
        await publisher.manifest_activated("m-001")
        s = publisher.status()
        assert s["failed"] == 1
        assert s["published"] == 0

    @pytest.mark.asyncio
    async def test_clear_client_stops_publishing(self, publisher, mock_client):
        publisher.clear_client()
        await publisher.manifest_activated("m-001")
        mock_client.publish.assert_not_awaited()
        assert publisher.status()["connected"] is False


# ---------------------------------------------------------------------------
# set_client / clear_client lifecycle
# ---------------------------------------------------------------------------

class TestClientLifecycle:
    def test_set_then_clear(self):
        p = PlayerEventPublisher()
        assert p.status()["connected"] is False
        client = MagicMock()
        p.set_client(client)
        assert p.status()["connected"] is True
        p.clear_client()
        assert p.status()["connected"] is False

    def test_replace_client(self):
        p = PlayerEventPublisher()
        c1 = MagicMock()
        c2 = MagicMock()
        p.set_client(c1)
        p.set_client(c2)
        assert p._client is c2
