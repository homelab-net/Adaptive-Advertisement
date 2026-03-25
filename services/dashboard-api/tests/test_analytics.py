"""
Tests for analytics router — audience summary, play events, campaign analytics,
and uptime SLO endpoints.

Uses the in-memory SQLite test DB (from conftest.py).
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient

from dashboard_api.models import AudienceSnapshot, PlayEvent, UptimeEvent, Campaign, CampaignManifest, Manifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot(
    minutes_ago: int = 5,
    count: int = 2,
    confidence: float = 0.8,
    suppressed: bool = True,
) -> AudienceSnapshot:
    return AudienceSnapshot(
        id=str(uuid.uuid4()),
        sampled_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        presence_count=count,
        presence_confidence=confidence,
        state_stable=True,
        pipeline_degraded=False,
        demographics_suppressed=suppressed,
        age_group_child=None,
        age_group_young_adult=None,
        age_group_adult=None,
        age_group_senior=None,
    )


def _play_event(manifest_id: str, minutes_ago: int = 10) -> PlayEvent:
    return PlayEvent(
        id=str(uuid.uuid4()),
        manifest_id=manifest_id,
        activated_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        reason="test",
        prev_manifest_id=None,
        received_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


def _uptime_event(status: str = "healthy", minutes_ago: int = 5) -> UptimeEvent:
    return UptimeEvent(
        id=str(uuid.uuid4()),
        sampled_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        player_status=status,
        overall_status="healthy" if status == "healthy" else "critical",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/summary
# ---------------------------------------------------------------------------

class TestAnalyticsSummary:

    async def test_no_data_returns_not_available(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_available"] is False
        assert body["total_observations"] == 0
        assert body["avg_count_per_window"] is None

    async def test_with_snapshots_returns_aggregated(self, client: AsyncClient, session):
        for i in range(3):
            session.add(_snapshot(minutes_ago=i * 5, count=i + 1))
        await session.flush()

        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_available"] is True
        assert body["total_observations"] == 3
        assert body["peak_count"] == 3
        assert body["avg_count_per_window"] is not None

    async def test_old_snapshots_excluded(self, client: AsyncClient, session):
        # > 1 hour old — should be excluded from rolling window
        session.add(_snapshot(minutes_ago=90, count=100))
        await session.flush()

        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_available"] is False

    async def test_response_has_required_fields(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        body = resp.json()
        for field in (
            "window_description", "sampled_at", "total_observations",
            "avg_count_per_window", "peak_count", "age_distribution", "data_available",
        ):
            assert field in body, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/play-events
# ---------------------------------------------------------------------------

class TestPlayEvents:

    async def test_empty_returns_empty_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/play-events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["pagination"]["total"] == 0

    async def test_returns_play_events(self, client: AsyncClient, session):
        session.add(_play_event("m-001"))
        session.add(_play_event("m-002"))
        await session.flush()

        resp = await client.get("/api/v1/analytics/play-events")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        assert len(body["items"]) == 2

    async def test_filter_by_manifest_id(self, client: AsyncClient, session):
        session.add(_play_event("m-alpha"))
        session.add(_play_event("m-alpha"))
        session.add(_play_event("m-beta"))
        await session.flush()

        resp = await client.get("/api/v1/analytics/play-events?manifest_id=m-alpha")
        assert resp.status_code == 200
        body = resp.json()
        assert body["pagination"]["total"] == 2
        for item in body["items"]:
            assert item["manifest_id"] == "m-alpha"

    async def test_event_fields_present(self, client: AsyncClient, session):
        session.add(_play_event("m-001"))
        await session.flush()

        resp = await client.get("/api/v1/analytics/play-events")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        for field in ("id", "manifest_id", "activated_at", "reason", "received_at"):
            assert field in item


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/campaigns/{id}/summary
# ---------------------------------------------------------------------------

class TestCampaignAnalytics:

    async def test_campaign_not_found_returns_404(self, client: AsyncClient):
        resp = await client.get(f"/api/v1/analytics/campaigns/{uuid.uuid4()}/summary")
        assert resp.status_code == 404

    async def test_campaign_with_no_impressions(self, client: AsyncClient, session):
        campaign = Campaign(
            id=str(uuid.uuid4()),
            name="Test Campaign",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(campaign)
        await session.flush()

        resp = await client.get(f"/api/v1/analytics/campaigns/{campaign.id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["campaign_id"] == campaign.id
        assert body["total_impressions"] == 0
        assert body["manifest_breakdown"] == []

    async def test_campaign_with_impressions(self, client: AsyncClient, session):
        now = datetime.now(timezone.utc)
        campaign = Campaign(
            id=str(uuid.uuid4()),
            name="Promo Campaign",
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(campaign)
        await session.flush()

        # Create a Manifest row so CampaignManifest FK is satisfied
        manifest = Manifest(
            id=str(uuid.uuid4()),
            manifest_id="m-promo",
            title="Promo",
            status="enabled",
            schema_version="1.0.0",
            created_at=now,
            updated_at=now,
        )
        session.add(manifest)
        await session.flush()

        # CampaignManifest.manifest_id is FK → manifests.id (UUID)
        cm = CampaignManifest(
            campaign_id=campaign.id,
            manifest_id=manifest.id,
            position=0,
            created_at=now,
        )
        session.add(cm)
        await session.flush()

        # PlayEvent.manifest_id stores ICD-5 string "m-promo"
        session.add(_play_event("m-promo"))
        session.add(_play_event("m-promo"))
        await session.flush()

        resp = await client.get(f"/api/v1/analytics/campaigns/{campaign.id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_impressions"] == 2
        assert len(body["manifest_breakdown"]) == 1
        assert body["manifest_breakdown"][0]["manifest_id"] == "m-promo"
        assert body["manifest_breakdown"][0]["impressions"] == 2


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/uptime
# ---------------------------------------------------------------------------

class TestUptimeSummary:

    async def test_no_data_returns_empty_summary(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/uptime")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_probes"] == 0
        assert body["uptime_pct"] is None
        assert body["slo_met"] is None

    async def test_all_healthy_probes(self, client: AsyncClient, session):
        for i in range(10):
            session.add(_uptime_event("healthy", minutes_ago=i * 5))
        await session.flush()

        resp = await client.get("/api/v1/analytics/uptime")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_probes"] == 10
        assert body["healthy_probes"] == 10
        assert body["uptime_pct"] == 100.0
        assert body["slo_met"] is True

    async def test_mixed_probes_computes_pct(self, client: AsyncClient, session):
        for i in range(9):
            session.add(_uptime_event("healthy", minutes_ago=i * 5))
        session.add(_uptime_event("unreachable", minutes_ago=50))
        await session.flush()

        resp = await client.get("/api/v1/analytics/uptime")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_probes"] == 10
        assert body["healthy_probes"] == 9
        assert body["uptime_pct"] == 90.0
        assert body["slo_met"] is False

    async def test_custom_hours_window(self, client: AsyncClient, session):
        # Verify the hours parameter is accepted and window_description reflects it
        for hours in [1, 2, 24, 168]:
            resp = await client.get(f"/api/v1/analytics/uptime?hours={hours}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["window_description"] == f"rolling {hours}h"
            assert "total_probes" in body
            assert "slo_target_pct" in body

        # hours out of range → 422
        resp_bad = await client.get("/api/v1/analytics/uptime?hours=0")
        assert resp_bad.status_code == 422

    async def test_response_has_required_fields(self, client: AsyncClient):
        resp = await client.get("/api/v1/analytics/uptime")
        assert resp.status_code == 200
        body = resp.json()
        for field in (
            "window_description", "sampled_at", "total_probes",
            "healthy_probes", "uptime_pct", "slo_target_pct", "slo_met",
        ):
            assert field in body
