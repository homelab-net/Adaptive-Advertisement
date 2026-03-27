"""
Tests for campaign management and manifest-to-campaign association.

Covers:
- CRUD for campaigns
- Adding approved/enabled manifests to campaigns (allowed)
- Adding draft/rejected manifests to campaigns (forbidden)
- Removing manifests
- Archiving campaigns
"""
import pytest
AsyncClient = pytest.importorskip("httpx").AsyncClient


async def _create_campaign(client: AsyncClient, name: str = "Test Campaign") -> dict:
    resp = await client.post("/api/v1/campaigns", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_and_approve_manifest(client: AsyncClient, manifest_id: str) -> dict:
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": manifest_id,
            "title": manifest_id,
            "schema_version": "1.0.0",
            "manifest_json": {"items": []},
        },
    )
    assert resp.status_code == 201
    resp = await client.post(
        f"/api/v1/manifests/{manifest_id}/approve",
        json={"approved_by": "ops"},
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def test_create_campaign(client: AsyncClient) -> None:
    data = await _create_campaign(client, "Summer Sale")
    assert data["name"] == "Summer Sale"
    assert data["status"] == "draft"
    assert data["manifest_ids"] == []


async def test_list_campaigns(client: AsyncClient) -> None:
    await _create_campaign(client, "Camp A")
    await _create_campaign(client, "Camp B")
    resp = await client.get("/api/v1/campaigns")
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] >= 2


async def test_get_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Get Me")
    resp = await client.get(f"/api/v1/campaigns/{camp['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Get Me"


async def test_get_campaign_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/campaigns/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Old Name")
    resp = await client.patch(
        f"/api/v1/campaigns/{camp['id']}",
        json={"name": "New Name", "status": "active"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["status"] == "active"


async def test_archive_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "To Archive")
    resp = await client.delete(f"/api/v1/campaigns/{camp['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_cannot_update_archived_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Archived Camp")
    await client.delete(f"/api/v1/campaigns/{camp['id']}")
    resp = await client.patch(
        f"/api/v1/campaigns/{camp['id']}",
        json={"name": "New Name"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Manifest association — enforcement of approval requirement
# ---------------------------------------------------------------------------

async def test_add_approved_manifest_to_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "With Manifest")
    await _create_and_approve_manifest(client, "camp-m-001")
    resp = await client.post(
        f"/api/v1/campaigns/{camp['id']}/manifests/camp-m-001"
    )
    assert resp.status_code == 200
    assert "camp-m-001" in resp.json()["manifest_ids"]


async def test_add_enabled_manifest_to_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "With Enabled")
    await _create_and_approve_manifest(client, "camp-m-enabled-001")
    await client.post("/api/v1/manifests/camp-m-enabled-001/enable")
    resp = await client.post(
        f"/api/v1/campaigns/{camp['id']}/manifests/camp-m-enabled-001"
    )
    assert resp.status_code == 200


async def test_cannot_add_draft_manifest_to_campaign(client: AsyncClient) -> None:
    """Non-bypassable: draft manifests cannot be added to campaigns."""
    camp = await _create_campaign(client, "Strict Camp")
    await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "draft-blocked-001",
            "title": "Draft",
            "schema_version": "1.0.0",
            "manifest_json": {},
        },
    )
    resp = await client.post(
        f"/api/v1/campaigns/{camp['id']}/manifests/draft-blocked-001"
    )
    assert resp.status_code == 409


async def test_cannot_add_rejected_manifest_to_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Strict Camp 2")
    await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "rejected-blocked-001",
            "title": "Rejected",
            "schema_version": "1.0.0",
            "manifest_json": {},
        },
    )
    await client.post(
        "/api/v1/manifests/rejected-blocked-001/reject",
        json={"reason": "Bad content", "rejected_by": "ops"},
    )
    resp = await client.post(
        f"/api/v1/campaigns/{camp['id']}/manifests/rejected-blocked-001"
    )
    assert resp.status_code == 409


async def test_add_manifest_idempotent(client: AsyncClient) -> None:
    """Adding the same manifest twice is idempotent."""
    camp = await _create_campaign(client, "Idempotent Camp")
    await _create_and_approve_manifest(client, "idem-m-001")
    await client.post(f"/api/v1/campaigns/{camp['id']}/manifests/idem-m-001")
    resp = await client.post(f"/api/v1/campaigns/{camp['id']}/manifests/idem-m-001")
    assert resp.status_code == 200
    assert resp.json()["manifest_ids"].count("idem-m-001") == 1


async def test_remove_manifest_from_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Remove Test")
    await _create_and_approve_manifest(client, "remove-m-001")
    await client.post(f"/api/v1/campaigns/{camp['id']}/manifests/remove-m-001")
    resp = await client.delete(f"/api/v1/campaigns/{camp['id']}/manifests/remove-m-001")
    assert resp.status_code == 200
    assert "remove-m-001" not in resp.json()["manifest_ids"]


async def test_remove_nonexistent_manifest_from_campaign(client: AsyncClient) -> None:
    camp = await _create_campaign(client, "Ghost Manifest")
    await _create_and_approve_manifest(client, "ghost-m-001")
    resp = await client.delete(f"/api/v1/campaigns/{camp['id']}/manifests/ghost-m-001")
    assert resp.status_code == 404
