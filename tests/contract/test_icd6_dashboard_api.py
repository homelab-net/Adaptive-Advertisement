"""
ICD-6/7 contract tests — dashboard-api REST schemas.

Covers four schemas:
  - contracts/dashboard-api/manifest-record.schema.json
  - contracts/dashboard-api/campaign-record.schema.json
  - contracts/dashboard-api/audit-event.schema.json
  - contracts/dashboard-api/system-status.schema.json
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

MANIFEST_SCHEMA = load_schema("dashboard-api/manifest-record.schema.json")
CAMPAIGN_SCHEMA = load_schema("dashboard-api/campaign-record.schema.json")
AUDIT_SCHEMA = load_schema("dashboard-api/audit-event.schema.json")
STATUS_SCHEMA = load_schema("dashboard-api/system-status.schema.json")


# ===========================================================================
# ManifestRecord
# ===========================================================================

@pytest.fixture()
def valid_manifest_record() -> dict:
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "manifest_id": "manifest-attract-01",
        "title": "Attract Loop — Coffee",
        "status": "approved",
        "schema_version": "1.0.0",
        "created_at": "2026-01-10T09:00:00Z",
        "updated_at": "2026-01-10T09:05:00Z",
    }


class TestManifestRecord:
    def test_minimal_valid(self, valid_manifest_record):
        assert_valid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_with_all_optional_fields(self, valid_manifest_record):
        valid_manifest_record.update({
            "manifest_json": {"schema_version": "1.0.0"},
            "rejection_reason": None,
            "approved_by": "operator",
            "approved_at": "2026-01-10T09:05:00Z",
            "enabled_at": "2026-01-10T09:06:00Z",
        })
        assert_valid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_null_optional_fields_valid(self, valid_manifest_record):
        valid_manifest_record.update({
            "manifest_json": None,
            "rejection_reason": None,
            "approved_by": None,
            "approved_at": None,
            "enabled_at": None,
        })
        assert_valid(MANIFEST_SCHEMA, valid_manifest_record)

    @pytest.mark.parametrize("status", [
        "draft", "approved", "rejected", "enabled", "disabled", "archived",
    ])
    def test_all_valid_statuses(self, valid_manifest_record, status):
        valid_manifest_record["status"] = status
        assert_valid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_invalid_status_rejected(self, valid_manifest_record):
        valid_manifest_record["status"] = "pending"
        assert_invalid(MANIFEST_SCHEMA, valid_manifest_record)

    @pytest.mark.parametrize("field", [
        "id", "manifest_id", "title", "status", "schema_version",
        "created_at", "updated_at",
    ])
    def test_missing_required_field_rejected(self, valid_manifest_record, field):
        del valid_manifest_record[field]
        assert_invalid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_empty_title_rejected(self, valid_manifest_record):
        valid_manifest_record["title"] = ""
        assert_invalid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_empty_manifest_id_rejected(self, valid_manifest_record):
        valid_manifest_record["manifest_id"] = ""
        assert_invalid(MANIFEST_SCHEMA, valid_manifest_record)

    def test_unknown_field_rejected(self, valid_manifest_record):
        valid_manifest_record["raw_content"] = "..."
        assert_invalid(MANIFEST_SCHEMA, valid_manifest_record)


# ===========================================================================
# CampaignRecord
# ===========================================================================

@pytest.fixture()
def valid_campaign() -> dict:
    return {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "name": "Spring Launch",
        "status": "draft",
        "created_at": "2026-01-12T08:00:00Z",
        "updated_at": "2026-01-12T08:00:00Z",
    }


class TestCampaignRecord:
    def test_minimal_valid(self, valid_campaign):
        assert_valid(CAMPAIGN_SCHEMA, valid_campaign)

    def test_with_all_optional_fields(self, valid_campaign):
        valid_campaign.update({
            "description": "Spring promotion across all sites.",
            "start_at": "2026-03-01T00:00:00Z",
            "end_at": "2026-04-30T23:59:59Z",
            "manifest_ids": ["manifest-01", "manifest-02"],
        })
        assert_valid(CAMPAIGN_SCHEMA, valid_campaign)

    def test_null_optional_date_fields(self, valid_campaign):
        valid_campaign["start_at"] = None
        valid_campaign["end_at"] = None
        assert_valid(CAMPAIGN_SCHEMA, valid_campaign)

    @pytest.mark.parametrize("status", ["draft", "active", "paused", "archived"])
    def test_all_valid_statuses(self, valid_campaign, status):
        valid_campaign["status"] = status
        assert_valid(CAMPAIGN_SCHEMA, valid_campaign)

    def test_invalid_status_rejected(self, valid_campaign):
        valid_campaign["status"] = "enabled"
        assert_invalid(CAMPAIGN_SCHEMA, valid_campaign)

    @pytest.mark.parametrize("field", ["id", "name", "status", "created_at", "updated_at"])
    def test_missing_required_field_rejected(self, valid_campaign, field):
        del valid_campaign[field]
        assert_invalid(CAMPAIGN_SCHEMA, valid_campaign)

    def test_empty_name_rejected(self, valid_campaign):
        valid_campaign["name"] = ""
        assert_invalid(CAMPAIGN_SCHEMA, valid_campaign)

    def test_unknown_field_rejected(self, valid_campaign):
        valid_campaign["owner"] = "admin"
        assert_invalid(CAMPAIGN_SCHEMA, valid_campaign)


# ===========================================================================
# AuditEvent
# ===========================================================================

@pytest.fixture()
def valid_audit_event() -> dict:
    return {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "event_type": "manifest.approved",
        "entity_type": "manifest",
        "entity_id": "manifest-attract-01",
        "actor": "operator",
        "created_at": "2026-01-10T09:05:00Z",
    }


class TestAuditEvent:
    def test_minimal_valid(self, valid_audit_event):
        assert_valid(AUDIT_SCHEMA, valid_audit_event)

    def test_with_payload(self, valid_audit_event):
        valid_audit_event["payload"] = {"previous_status": "draft"}
        assert_valid(AUDIT_SCHEMA, valid_audit_event)

    def test_null_payload(self, valid_audit_event):
        valid_audit_event["payload"] = None
        assert_valid(AUDIT_SCHEMA, valid_audit_event)

    @pytest.mark.parametrize("event_type", [
        "manifest.created", "manifest.approved", "manifest.rejected",
        "manifest.enabled", "manifest.disabled", "manifest.archived",
        "campaign.created", "campaign.updated", "campaign.archived",
        "campaign.manifest_added", "campaign.manifest_removed",
        "asset.uploaded", "asset.archived",
        "safe_mode.engaged", "safe_mode.cleared",
    ])
    def test_all_valid_event_types(self, valid_audit_event, event_type):
        valid_audit_event["event_type"] = event_type
        # Adjust entity_type to match
        if event_type.startswith("campaign"):
            valid_audit_event["entity_type"] = "campaign"
        elif event_type.startswith("asset"):
            valid_audit_event["entity_type"] = "asset"
        elif event_type.startswith("safe_mode"):
            valid_audit_event["entity_type"] = "system"
        assert_valid(AUDIT_SCHEMA, valid_audit_event)

    def test_invalid_event_type_rejected(self, valid_audit_event):
        valid_audit_event["event_type"] = "manifest.deleted"
        assert_invalid(AUDIT_SCHEMA, valid_audit_event)

    @pytest.mark.parametrize("entity_type", ["manifest", "campaign", "asset", "system"])
    def test_all_valid_entity_types(self, valid_audit_event, entity_type):
        valid_audit_event["entity_type"] = entity_type
        assert_valid(AUDIT_SCHEMA, valid_audit_event)

    def test_invalid_entity_type_rejected(self, valid_audit_event):
        valid_audit_event["entity_type"] = "user"
        assert_invalid(AUDIT_SCHEMA, valid_audit_event)

    @pytest.mark.parametrize("field", [
        "id", "event_type", "entity_type", "entity_id", "actor", "created_at",
    ])
    def test_missing_required_field_rejected(self, valid_audit_event, field):
        del valid_audit_event[field]
        assert_invalid(AUDIT_SCHEMA, valid_audit_event)

    def test_unknown_field_rejected(self, valid_audit_event):
        valid_audit_event["ip_address"] = "192.168.1.1"
        assert_invalid(AUDIT_SCHEMA, valid_audit_event)


# ===========================================================================
# SystemStatus
# ===========================================================================

@pytest.fixture()
def valid_system_status() -> dict:
    return {
        "sampled_at": "2026-01-15T12:00:00Z",
        "overall": "healthy",
        "safe_mode": {"active": False, "reason": None, "activated_at": None},
        "services": {
            "player": {
                "status": "healthy",
                "probed_at": "2026-01-15T12:00:00Z",
                "latency_ms": 12,
                "detail": None,
            },
            "decision-optimizer": {
                "status": "healthy",
                "probed_at": "2026-01-15T12:00:00Z",
            },
        },
    }


class TestSystemStatus:
    def test_minimal_valid(self, valid_system_status):
        assert_valid(STATUS_SCHEMA, valid_system_status)

    def test_safe_mode_active(self, valid_system_status):
        valid_system_status["safe_mode"] = {
            "active": True,
            "reason": "supervisor_escalation",
            "activated_at": "2026-01-15T11:55:00Z",
        }
        assert_valid(STATUS_SCHEMA, valid_system_status)

    @pytest.mark.parametrize("overall", ["healthy", "degraded", "critical"])
    def test_all_overall_statuses(self, valid_system_status, overall):
        valid_system_status["overall"] = overall
        assert_valid(STATUS_SCHEMA, valid_system_status)

    def test_invalid_overall_status_rejected(self, valid_system_status):
        valid_system_status["overall"] = "unknown"
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    @pytest.mark.parametrize("svc_status", ["healthy", "unhealthy", "unreachable"])
    def test_all_service_statuses(self, valid_system_status, svc_status):
        valid_system_status["services"]["player"]["status"] = svc_status
        assert_valid(STATUS_SCHEMA, valid_system_status)

    def test_invalid_service_status_rejected(self, valid_system_status):
        valid_system_status["services"]["player"]["status"] = "degraded"
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    @pytest.mark.parametrize("field", ["sampled_at", "overall", "safe_mode", "services"])
    def test_missing_required_field_rejected(self, valid_system_status, field):
        del valid_system_status[field]
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_missing_safe_mode_active_rejected(self, valid_system_status):
        valid_system_status["safe_mode"] = {"reason": None}
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_missing_service_status_rejected(self, valid_system_status):
        del valid_system_status["services"]["player"]["status"]
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_missing_service_probed_at_rejected(self, valid_system_status):
        del valid_system_status["services"]["player"]["probed_at"]
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_latency_ms_negative_rejected(self, valid_system_status):
        valid_system_status["services"]["player"]["latency_ms"] = -1
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_unknown_top_level_field_rejected(self, valid_system_status):
        valid_system_status["uptime_s"] = 86400
        assert_invalid(STATUS_SCHEMA, valid_system_status)

    def test_unknown_safe_mode_field_rejected(self, valid_system_status):
        valid_system_status["safe_mode"]["operator"] = "admin"
        assert_invalid(STATUS_SCHEMA, valid_system_status)
