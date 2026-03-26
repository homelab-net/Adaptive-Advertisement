"""
Tests for audience tag endpoints on manifests:
  - audience_tags field on create and in responses
  - PATCH /api/v1/manifests/{id}/tags
  - GET  /api/v1/manifests/{id}/rule-preview
  - POST /api/v1/manifests/sync-rules
"""
import pytest
from typing import Any

AsyncClient = Any

MANIFEST_JSON = {
    "schema_version": "1.0.0",
    "manifest_id": "test-tags-001",
    "items": [{"item_id": "i1", "asset_id": "a1", "asset_type": "image", "duration_ms": 10000}],
}


async def _create(
    client: AsyncClient,
    manifest_id: str = "tags-m-001",
    tags: list[str] | None = None,
) -> dict:
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": manifest_id,
            "title": f"Test {manifest_id}",
            "schema_version": "1.0.0",
            "manifest_json": {**MANIFEST_JSON, "manifest_id": manifest_id},
            "audience_tags": tags or [],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# audience_tags on create
# ---------------------------------------------------------------------------

async def test_create_manifest_with_tags(client: AsyncClient) -> None:
    data = await _create(client, "create-tag-001", tags=["adult_with_child", "time_happy_hour"])
    assert data["audience_tags"] == ["adult_with_child", "time_happy_hour"]


async def test_create_manifest_no_tags_returns_empty_list(client: AsyncClient) -> None:
    data = await _create(client, "create-notag-001")
    assert data["audience_tags"] == []


async def test_create_manifest_invalid_tag_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "invalid-tag-001",
            "title": "Bad Tags",
            "schema_version": "1.0.0",
            "manifest_json": MANIFEST_JSON,
            "audience_tags": ["not_a_real_tag"],
        },
    )
    assert resp.status_code == 422


async def test_create_manifest_duplicate_tag_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "dup-tag-001",
            "title": "Dup Tags",
            "schema_version": "1.0.0",
            "manifest_json": MANIFEST_JSON,
            "audience_tags": ["general", "general"],
        },
    )
    assert resp.status_code == 422


async def test_tags_appear_in_list_view(client: AsyncClient) -> None:
    await _create(client, "listtag-001", tags=["solo_adult"])
    resp = await client.get("/api/v1/manifests?status=draft")
    assert resp.status_code == 200
    items = resp.json()["items"]
    found = next((i for i in items if i["manifest_id"] == "listtag-001"), None)
    assert found is not None
    assert "solo_adult" in found["audience_tags"]


async def test_tags_appear_in_get_response(client: AsyncClient) -> None:
    await _create(client, "gettag-001", tags=["seniors", "time_evening"])
    resp = await client.get("/api/v1/manifests/gettag-001")
    assert resp.status_code == 200
    assert "seniors" in resp.json()["audience_tags"]
    assert "time_evening" in resp.json()["audience_tags"]


# ---------------------------------------------------------------------------
# PATCH /api/v1/manifests/{id}/tags
# ---------------------------------------------------------------------------

async def test_update_tags_on_draft(client: AsyncClient) -> None:
    await _create(client, "patch-tag-001", tags=["general"])
    resp = await client.patch(
        "/api/v1/manifests/patch-tag-001/tags",
        json={"audience_tags": ["adult_with_child", "time_happy_hour", "promo_featured"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["audience_tags"]) == {"adult_with_child", "time_happy_hour", "promo_featured"}


async def test_update_tags_to_empty_list(client: AsyncClient) -> None:
    await _create(client, "patch-empty-001", tags=["general"])
    resp = await client.patch(
        "/api/v1/manifests/patch-empty-001/tags",
        json={"audience_tags": []},
    )
    assert resp.status_code == 200
    assert resp.json()["audience_tags"] == []


async def test_update_tags_invalid_key_returns_422(client: AsyncClient) -> None:
    await _create(client, "patch-bad-001")
    resp = await client.patch(
        "/api/v1/manifests/patch-bad-001/tags",
        json={"audience_tags": ["unknown_tag_xyz"]},
    )
    assert resp.status_code == 422


async def test_update_tags_duplicate_returns_422(client: AsyncClient) -> None:
    await _create(client, "patch-dup-001")
    resp = await client.patch(
        "/api/v1/manifests/patch-dup-001/tags",
        json={"audience_tags": ["general", "general"]},
    )
    assert resp.status_code == 422


async def test_update_tags_on_archived_returns_409(client: AsyncClient) -> None:
    await _create(client, "patch-arch-001")
    await client.delete("/api/v1/manifests/patch-arch-001")  # archive
    resp = await client.patch(
        "/api/v1/manifests/patch-arch-001/tags",
        json={"audience_tags": ["general"]},
    )
    assert resp.status_code == 409


async def test_update_tags_does_not_change_status(client: AsyncClient) -> None:
    await _create(client, "patch-status-001", tags=["general"])
    await client.post("/api/v1/manifests/patch-status-001/approve", json={"approved_by": "ops"})
    resp = await client.patch(
        "/api/v1/manifests/patch-status-001/tags",
        json={"audience_tags": ["solo_adult"]},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_update_tags_on_enabled_manifest(client: AsyncClient) -> None:
    """Tags can be updated on enabled manifests (takes effect after sync-rules)."""
    await _create(client, "patch-enabled-001", tags=["general"])
    await client.post("/api/v1/manifests/patch-enabled-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/patch-enabled-001/enable")
    resp = await client.patch(
        "/api/v1/manifests/patch-enabled-001/tags",
        json={"audience_tags": ["adult_with_child", "freq_recurring"]},
    )
    assert resp.status_code == 200
    assert "adult_with_child" in resp.json()["audience_tags"]
    assert resp.json()["status"] == "enabled"


async def test_update_tags_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/v1/manifests/does-not-exist/tags",
        json={"audience_tags": ["general"]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/manifests/{id}/rule-preview
# ---------------------------------------------------------------------------

async def test_rule_preview_returns_generated_rules(client: AsyncClient) -> None:
    await _create(client, "preview-001", tags=["time_happy_hour", "adult_with_child"])
    resp = await client.get("/api/v1/manifests/preview-001/rule-preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest_id"] == "preview-001"
    assert "adult_with_child" in data["audience_tags"]
    assert len(data["generated_rules"]) >= 1
    # The rule should have time conditions
    rule = data["generated_rules"][0]
    assert rule["conditions"].get("time_hour_gte") == 16
    assert rule["conditions"].get("time_hour_lte") == 18


async def test_rule_preview_no_tags_returns_empty_rules(client: AsyncClient) -> None:
    await _create(client, "preview-empty-001")
    resp = await client.get("/api/v1/manifests/preview-empty-001/rule-preview")
    assert resp.status_code == 200
    assert resp.json()["generated_rules"] == []


async def test_rule_preview_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/manifests/no-such/rule-preview")
    assert resp.status_code == 404


async def test_rule_preview_freq_recurring_shows_reminder_rule(client: AsyncClient) -> None:
    await _create(client, "preview-recurring-001", tags=["time_morning", "general", "freq_recurring"])
    resp = await client.get("/api/v1/manifests/preview-recurring-001/rule-preview")
    assert resp.status_code == 200
    rules = resp.json()["generated_rules"]
    reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
    assert len(reminder_rules) == 1
    assert reminder_rules[0]["weight"] < 1.0


async def test_rule_preview_is_read_only(client: AsyncClient) -> None:
    """Calling rule-preview twice should return the same result."""
    await _create(client, "preview-idempotent-001", tags=["general"])
    r1 = await client.get("/api/v1/manifests/preview-idempotent-001/rule-preview")
    r2 = await client.get("/api/v1/manifests/preview-idempotent-001/rule-preview")
    assert r1.json() == r2.json()


# ---------------------------------------------------------------------------
# POST /api/v1/manifests/sync-rules
# ---------------------------------------------------------------------------

async def test_sync_rules_returns_ok_structure(client: AsyncClient) -> None:
    """sync-rules always returns 200 with the expected response fields."""
    resp = await client.post("/api/v1/manifests/sync-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["enabled_manifests"], int)
    assert isinstance(data["generated_rules"], int)
    assert isinstance(data["has_fallback"], bool)
    assert isinstance(data["optimizer_reloaded"], bool)
    # The fallback is always True: either an attract/empty rule exists, or
    # the safety fallback was injected because no catch-all is present.
    assert data["has_fallback"] is True


async def test_sync_rules_with_enabled_manifest(client: AsyncClient, tmp_path) -> None:
    """
    Create → approve → enable a tagged manifest, then sync-rules.
    The response should reflect the generated rule count.
    """
    await _create(client, "sync-001", tags=["attract"])
    await client.post("/api/v1/manifests/sync-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/sync-001/enable")

    resp = await client.post("/api/v1/manifests/sync-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["enabled_manifests"] >= 1
    assert data["generated_rules"] >= 1


async def test_sync_rules_attract_tag_has_fallback(client: AsyncClient) -> None:
    """An enabled manifest with attract tag provides the catch-all — no safety fallback needed."""
    await _create(client, "sync-attract-001", tags=["attract"])
    await client.post("/api/v1/manifests/sync-attract-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/sync-attract-001/enable")

    resp = await client.post("/api/v1/manifests/sync-rules")
    assert resp.status_code == 200
    # has_fallback should be True because attract = empty conditions = catch-all
    assert resp.json()["has_fallback"] is True


async def test_sync_rules_with_freq_recurring_generates_reminder(client: AsyncClient) -> None:
    await _create(client, "sync-recurring-001", tags=["time_happy_hour", "general", "freq_recurring"])
    await client.post("/api/v1/manifests/sync-recurring-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/sync-recurring-001/enable")

    resp = await client.post("/api/v1/manifests/sync-rules")
    assert resp.status_code == 200
    data = resp.json()
    # Should generate at least 2 rules: time window rule + reminder
    assert data["generated_rules"] >= 2


async def test_sync_rules_multiple_enabled_manifests(client: AsyncClient) -> None:
    for i in range(3):
        mid = f"sync-multi-{i:03d}"
        await _create(client, mid, tags=["general"])
        await client.post(f"/api/v1/manifests/{mid}/approve", json={"approved_by": "ops"})
        await client.post(f"/api/v1/manifests/{mid}/enable")

    resp = await client.post("/api/v1/manifests/sync-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled_manifests"] >= 3


async def test_sync_rules_idempotent(client: AsyncClient) -> None:
    """Calling sync-rules twice should succeed both times."""
    await _create(client, "sync-idem-001", tags=["general"])
    await client.post("/api/v1/manifests/sync-idem-001/approve", json={"approved_by": "ops"})
    await client.post("/api/v1/manifests/sync-idem-001/enable")

    r1 = await client.post("/api/v1/manifests/sync-rules")
    r2 = await client.post("/api/v1/manifests/sync-rules")
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Tag taxonomy — time tags via API
# ---------------------------------------------------------------------------

async def test_all_time_tags_accepted(client: AsyncClient) -> None:
    """All canonical time tags must be accepted by the create endpoint."""
    time_tags = [
        "time_morning", "time_lunch", "time_afternoon",
        "time_happy_hour", "time_evening", "time_late_night", "time_all_day",
    ]
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "time-tags-all-001",
            "title": "All Time Tags",
            "schema_version": "1.0.0",
            "manifest_json": MANIFEST_JSON,
            "audience_tags": time_tags,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert set(data["audience_tags"]) == set(time_tags)


async def test_all_promo_tags_accepted(client: AsyncClient) -> None:
    promo_tags = ["promo_featured", "promo_limited_time", "promo_seasonal"]
    resp = await client.post(
        "/api/v1/manifests",
        json={
            "manifest_id": "promo-tags-all-001",
            "title": "All Promo Tags",
            "schema_version": "1.0.0",
            "manifest_json": MANIFEST_JSON,
            "audience_tags": promo_tags,
        },
    )
    assert resp.status_code == 201, resp.text


async def test_all_freq_tags_accepted(client: AsyncClient) -> None:
    for i, tag in enumerate(["freq_primary", "freq_recurring", "freq_ambient"]):
        resp = await client.post(
            "/api/v1/manifests",
            json={
                "manifest_id": f"freq-tag-{i}",
                "title": f"Freq Tag {tag}",
                "schema_version": "1.0.0",
                "manifest_json": MANIFEST_JSON,
                "audience_tags": [tag],
            },
        )
        assert resp.status_code == 201, f"Failed for tag {tag}: {resp.text}"


async def test_happy_hour_with_adult_child_and_recurring(client: AsyncClient) -> None:
    """
    Full happy-path scenario: happy hour ad tagged for adults with children,
    featured promo, appearing sporadically throughout the day.
    """
    tags = ["time_happy_hour", "adult_with_child", "promo_featured", "freq_recurring"]
    data = await _create(client, "happy-hour-full-001", tags=tags)
    assert set(data["audience_tags"]) == set(tags)

    # Rule preview should show: time-window rule + reminder rule
    resp = await client.get("/api/v1/manifests/happy-hour-full-001/rule-preview")
    assert resp.status_code == 200
    rules = resp.json()["generated_rules"]
    # At least: 1 time×audience rule + 1 reminder
    assert len(rules) >= 2
    reminder_rules = [r for r in rules if "reminder" in r["rule_id"]]
    assert len(reminder_rules) == 1
    primary_rules = [r for r in rules if "reminder" not in r["rule_id"]]
    # Primary rule should have higher priority than reminder
    assert primary_rules[0]["priority"] > reminder_rules[0]["priority"]
    # Primary rule should have time conditions
    assert primary_rules[0]["conditions"]["time_hour_gte"] == 16
    assert primary_rules[0]["conditions"]["time_hour_lte"] == 18
    # Reminder rule should NOT have time conditions
    assert "time_hour_gte" not in reminder_rules[0]["conditions"]
