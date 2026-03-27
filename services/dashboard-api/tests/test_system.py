"""
Tests for system status, safe-mode control, and audit event log.
"""
import pytest
AsyncClient = pytest.importorskip("httpx").AsyncClient


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readyz_with_db(client: AsyncClient) -> None:
    """readyz should return 200 when the test DB (SQLite) is connected."""
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["db"] == "ok"


# ---------------------------------------------------------------------------
# Safe mode
# ---------------------------------------------------------------------------

async def test_get_safe_mode_default(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/safe-mode")
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is False


async def test_engage_safe_mode(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/safe-mode",
        json={"reason": "Operator override test", "activated_by": "ops"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["reason"] == "Operator override test"
    assert data["activated_at"] is not None


async def test_engage_safe_mode_idempotent(client: AsyncClient) -> None:
    """Engaging safe mode when already active is idempotent."""
    # Ensure clean state first
    await client.delete("/api/v1/safe-mode?cleared_by=ops")
    await client.post(
        "/api/v1/safe-mode",
        json={"reason": "First engage", "activated_by": "ops"},
    )
    resp = await client.post(
        "/api/v1/safe-mode",
        json={"reason": "Second engage", "activated_by": "ops"},
    )
    assert resp.status_code == 200
    # Reason should remain from first engagement (idempotent)
    assert resp.json()["reason"] == "First engage"


async def test_clear_safe_mode(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/safe-mode",
        json={"reason": "Test", "activated_by": "ops"},
    )
    resp = await client.delete("/api/v1/safe-mode?cleared_by=ops")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


async def test_clear_safe_mode_when_not_active(client: AsyncClient) -> None:
    """Clearing safe mode when not active returns active=False (idempotent)."""
    resp = await client.delete("/api/v1/safe-mode?cleared_by=ops")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

async def test_audit_events_created_on_manifest_actions(client: AsyncClient) -> None:
    """Manifest operations should generate audit events."""
    # Create
    await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "audit-test-001",
            "title": "Audit Test",
            "schema_version": "1.0.0",
            "manifest_json": {},
        },
    )
    # Approve
    await client.post(
        "/api/v1/manifests/audit-test-001/approve",
        json={"approved_by": "ops"},
    )

    resp = await client.get(
        "/api/v1/events?entity_id=audit-test-001"
    )
    assert resp.status_code == 200
    events = resp.json()["items"]
    event_types = [e["event_type"] for e in events]
    assert "manifest.created" in event_types
    assert "manifest.approved" in event_types


async def test_audit_events_safe_mode(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/safe-mode",
        json={"reason": "Audit safe mode test", "activated_by": "ops"},
    )
    await client.delete("/api/v1/safe-mode?cleared_by=ops")

    resp = await client.get("/api/v1/events?entity_type=system")
    assert resp.status_code == 200
    event_types = [e["event_type"] for e in resp.json()["items"]]
    assert "safe_mode.engaged" in event_types
    assert "safe_mode.cleared" in event_types


async def test_audit_events_pagination(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/events?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "pagination" in data
    assert len(data["items"]) <= 5


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

async def test_analytics_summary_scaffold(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_available"] is False
    assert "sampled_at" in data
    assert data["total_observations"] == 0
