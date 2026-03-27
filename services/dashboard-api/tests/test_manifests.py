"""
Tests for manifest CRUD and approval state machine (ICD-6).

Covers:
- Create manifest (draft)
- List and get manifests
- Full approval happy path: draft → approved → enabled → disabled
- Reject from draft; re-approve
- Invalid transitions (409 Conflict)
- Archive (terminal state — no further transitions)
- Duplicate manifest_id rejection
"""
import pytest
AsyncClient = pytest.importorskip("httpx").AsyncClient

MANIFEST_JSON = {
    "schema_version": "1.0.0",
    "manifest_id": "test-manifest-001",
    "tenant_id": "t1",
    "site_id": "s1",
    "approved": True,
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_until": "2027-01-01T00:00:00Z",
    "items": [
        {
            "item_id": "item-001",
            "asset_id": "asset-abc",
            "asset_type": "image",
            "duration_ms": 10000,
            "loop": False,
        }
    ],
}


async def _create(client: AsyncClient, manifest_id: str = "m-001") -> dict:
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": manifest_id,
            "title": "Test Manifest",
            "schema_version": "1.0.0",
            "manifest_json": {**MANIFEST_JSON, "manifest_id": manifest_id},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

async def test_create_manifest(client: AsyncClient) -> None:
    data = await _create(client, "create-001")
    assert data["manifest_id"] == "create-001"
    assert data["status"] == "draft"
    assert data["title"] == "Test Manifest"
    assert data["manifest_json"] is not None


async def test_create_manifest_duplicate_id(client: AsyncClient) -> None:
    await _create(client, "dup-001")
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "dup-001",
            "title": "Duplicate",
            "schema_version": "1.0.0",
            "manifest_json": MANIFEST_JSON,
        },
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

async def test_list_manifests(client: AsyncClient) -> None:
    await _create(client, "list-001")
    await _create(client, "list-002")
    resp = await client.get("/api/v1/manifests")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "pagination" in data
    assert data["pagination"]["total"] >= 2


async def test_list_manifests_status_filter(client: AsyncClient) -> None:
    await _create(client, "filter-001")
    resp = await client.get("/api/v1/manifests?status=draft")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["status"] == "draft" for i in items)


async def test_get_manifest_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/manifests/does-not-exist")
    assert resp.status_code == 404


async def test_get_manifest(client: AsyncClient) -> None:
    await _create(client, "get-001")
    resp = await client.get("/api/v1/manifests/get-001")
    assert resp.status_code == 200
    assert resp.json()["manifest_id"] == "get-001"


# ---------------------------------------------------------------------------
# Approval state machine — happy path
# ---------------------------------------------------------------------------

async def test_approve_manifest(client: AsyncClient) -> None:
    await _create(client, "approve-001")
    resp = await client.post(
        "/api/v1/manifests/approve-001/approve",
        json={"approved_by": "ops-team"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "ops-team"
    assert data["approved_at"] is not None


async def test_enable_manifest(client: AsyncClient) -> None:
    await _create(client, "enable-001")
    await client.post("/api/v1/manifests/enable-001/approve", json={"approved_by": "ops"})
    resp = await client.post("/api/v1/manifests/enable-001/enable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "enabled"


async def test_disable_manifest(client: AsyncClient) -> None:
    await _create(client, "disable-001")
    await client.post("/api/v1/manifests/disable-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/disable-001/enable")
    resp = await client.post("/api/v1/manifests/disable-001/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


async def test_reenable_disabled_manifest(client: AsyncClient) -> None:
    await _create(client, "reenable-001")
    await client.post("/api/v1/manifests/reenable-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/reenable-001/enable")
    await client.post("/api/v1/manifests/reenable-001/disable")
    resp = await client.post("/api/v1/manifests/reenable-001/enable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "enabled"


# ---------------------------------------------------------------------------
# Approval state machine — reject / reapprove
# ---------------------------------------------------------------------------

async def test_reject_manifest(client: AsyncClient) -> None:
    await _create(client, "reject-001")
    resp = await client.post(
        "/api/v1/manifests/reject-001/reject",
        json={"reason": "Missing required field.", "rejected_by": "ops"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Missing required field."


async def test_reapprove_rejected_manifest(client: AsyncClient) -> None:
    await _create(client, "reapprove-001")
    await client.post(
        "/api/v1/manifests/reapprove-001/reject",
        json={"reason": "Fix needed.", "rejected_by": "ops"},
    )
    resp = await client.post(
        "/api/v1/manifests/reapprove-001/approve",
        json={"approved_by": "ops"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Invalid transitions (non-bypassable approval enforcement)
# ---------------------------------------------------------------------------

async def test_cannot_enable_draft(client: AsyncClient) -> None:
    """Draft manifests cannot be enabled without approval."""
    await _create(client, "nodirect-001")
    resp = await client.post("/api/v1/manifests/nodirect-001/enable")
    assert resp.status_code == 409


async def test_cannot_disable_approved(client: AsyncClient) -> None:
    """Approved manifests cannot be disabled — must be enabled first."""
    await _create(client, "nodisable-001")
    await client.post("/api/v1/manifests/nodisable-001/approve", json={"approved_by": "ops"})
    resp = await client.post("/api/v1/manifests/nodisable-001/disable")
    assert resp.status_code == 409


async def test_cannot_approve_enabled(client: AsyncClient) -> None:
    """Enabled manifests cannot be re-approved."""
    await _create(client, "noreapprove-001")
    await client.post("/api/v1/manifests/noreapprove-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/noreapprove-001/enable")
    resp = await client.post(
        "/api/v1/manifests/noreapprove-001/approve", json={"approved_by": "ops"}
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Archive (terminal)
# ---------------------------------------------------------------------------

async def test_archive_manifest(client: AsyncClient) -> None:
    await _create(client, "archive-001")
    resp = await client.delete("/api/v1/manifests/archive-001")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


async def test_cannot_approve_archived(client: AsyncClient) -> None:
    """Archived is a terminal state."""
    await _create(client, "terminal-001")
    await client.delete("/api/v1/manifests/terminal-001")
    resp = await client.post(
        "/api/v1/manifests/terminal-001/approve", json={"approved_by": "ops"}
    )
    assert resp.status_code == 409


async def test_cannot_archive_already_archived(client: AsyncClient) -> None:
    await _create(client, "dblarchive-001")
    await client.delete("/api/v1/manifests/dblarchive-001")
    resp = await client.delete("/api/v1/manifests/dblarchive-001")
    assert resp.status_code == 409
