"""
ICD-5 contract tests — CreativeManifest (creative service → player).

Schema: contracts/creative/creative-manifest.schema.json  v1.0

Approval fields (approved_at, approved_by) are required.
Player must reject any manifest missing these fields — approval bypass
is a locked invariant.
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("creative/creative-manifest.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid() -> dict:
    return {
        "schema_version": "1.0.0",
        "manifest_id": "manifest-attract-01",
        "approved_at": "2026-01-10T09:00:00Z",
        "approved_by": "operator",
        "items": [
            {
                "item_id": "item-01",
                "asset_id": "coffee-promo.mp4",
                "asset_type": "video",
                "duration_ms": 15000,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidManifest:
    def test_minimal_valid_manifest(self, valid):
        assert_valid(SCHEMA, valid)

    def test_multiple_items(self, valid):
        valid["items"].append({
            "item_id": "item-02",
            "asset_id": "loyalty-card.jpg",
            "asset_type": "image",
            "duration_ms": 5000,
        })
        assert_valid(SCHEMA, valid)

    def test_all_asset_types(self, valid):
        for asset_type in ("video", "image", "html"):
            valid["items"][0]["asset_type"] = asset_type
            assert_valid(SCHEMA, valid)

    def test_with_loop_flag(self, valid):
        valid["items"][0]["loop"] = True
        assert_valid(SCHEMA, valid)

    def test_with_expires_at(self, valid):
        valid["expires_at"] = "2026-12-31T23:59:59Z"
        assert_valid(SCHEMA, valid)

    def test_with_full_policy(self, valid):
        valid["policy"] = {
            "min_dwell_ms": 5000,
            "cooldown_ms": 30000,
            "allow_interruption": False,
        }
        assert_valid(SCHEMA, valid)

    def test_minimum_duration_ms(self, valid):
        valid["items"][0]["duration_ms"] = 1000
        assert_valid(SCHEMA, valid)

    def test_html_asset(self, valid):
        valid["items"][0]["asset_type"] = "html"
        valid["items"][0]["asset_id"] = "dynamic-menu.html"
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Approval enforcement — locked invariant
# Missing approval fields must be rejected. Player cannot render without them.
# ---------------------------------------------------------------------------

class TestApprovalEnforcement:
    def test_missing_approved_at_rejected(self, valid):
        del valid["approved_at"]
        assert_invalid(SCHEMA, valid)

    def test_missing_approved_by_rejected(self, valid):
        del valid["approved_by"]
        assert_invalid(SCHEMA, valid)

    def test_empty_approved_by_rejected(self, valid):
        valid["approved_by"] = ""
        assert_invalid(SCHEMA, valid)

    def test_empty_manifest_id_rejected(self, valid):
        valid["manifest_id"] = ""
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "manifest_id", "approved_at", "approved_by", "items",
    ])
    def test_missing_required_field_rejected(self, valid, field):
        del valid[field]
        assert_invalid(SCHEMA, valid)

    @pytest.mark.parametrize("field", ["item_id", "asset_id", "asset_type", "duration_ms"])
    def test_missing_item_required_field_rejected(self, valid, field):
        del valid["items"][0][field]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# items constraints
# ---------------------------------------------------------------------------

class TestItemsConstraints:
    def test_empty_items_list_rejected(self, valid):
        valid["items"] = []
        assert_invalid(SCHEMA, valid)

    def test_unknown_asset_type_rejected(self, valid):
        valid["items"][0]["asset_type"] = "audio"
        assert_invalid(SCHEMA, valid)

    def test_duration_ms_below_1000_rejected(self, valid):
        valid["items"][0]["duration_ms"] = 999
        assert_invalid(SCHEMA, valid)

    def test_duration_ms_zero_rejected(self, valid):
        valid["items"][0]["duration_ms"] = 0
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_wrong_version_rejected(self, valid):
        valid["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_top_level_field_rejected(self, valid):
        valid["auto_approved"] = True
        assert_invalid(SCHEMA, valid)

    def test_unknown_item_field_rejected(self, valid):
        valid["items"][0]["priority"] = 1
        assert_invalid(SCHEMA, valid)

    def test_unknown_policy_field_rejected(self, valid):
        valid["policy"] = {"min_dwell_ms": 5000, "skip_approval": True}
        assert_invalid(SCHEMA, valid)
