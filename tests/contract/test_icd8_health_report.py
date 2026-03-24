"""
ICD-8 contract tests — ServiceHealthReport (supervisor ↔ managed services).

Schema: contracts/supervisor/service-health-report.schema.json  v1.0
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("supervisor/service-health-report.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def valid() -> dict:
    return {
        "schema_version": "1.0.0",
        "name": "player",
        "is_healthy": True,
        "consecutive_failures": 0,
        "restart_count": 0,
        "in_boot_loop": False,
        "escalated": False,
        "sampled_at": "2026-01-15T12:00:00Z",
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidReport:
    def test_minimal_valid_healthy(self, valid):
        assert_valid(SCHEMA, valid)

    def test_unhealthy_with_failures(self, valid):
        valid["is_healthy"] = False
        valid["consecutive_failures"] = 3
        valid["restart_count"] = 2
        valid["last_restart_at"] = "2026-01-15T11:58:00Z"
        assert_valid(SCHEMA, valid)

    def test_in_boot_loop(self, valid):
        valid["is_healthy"] = False
        valid["consecutive_failures"] = 5
        valid["restart_count"] = 5
        valid["in_boot_loop"] = True
        valid["escalated"] = True
        valid["last_restart_at"] = "2026-01-15T11:59:00Z"
        assert_valid(SCHEMA, valid)

    def test_last_restart_at_null(self, valid):
        valid["last_restart_at"] = None
        assert_valid(SCHEMA, valid)

    @pytest.mark.parametrize("name", [
        "player", "decision-optimizer", "audience-state",
        "creative", "dashboard-api", "supervisor",
    ])
    def test_known_service_names(self, valid, name):
        valid["name"] = name
        assert_valid(SCHEMA, valid)

    def test_high_restart_count(self, valid):
        valid["restart_count"] = 999
        valid["consecutive_failures"] = 10
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "name", "is_healthy", "consecutive_failures",
        "restart_count", "in_boot_loop", "escalated", "sampled_at",
    ])
    def test_missing_required_field_rejected(self, valid, field):
        del valid[field]
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Schema version
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_wrong_version_rejected(self, valid):
        valid["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

class TestNumericBounds:
    def test_consecutive_failures_negative_rejected(self, valid):
        valid["consecutive_failures"] = -1
        assert_invalid(SCHEMA, valid)

    def test_restart_count_negative_rejected(self, valid):
        valid["restart_count"] = -1
        assert_invalid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# name field
# ---------------------------------------------------------------------------

class TestNameField:
    def test_empty_name_rejected(self, valid):
        valid["name"] = ""
        assert_invalid(SCHEMA, valid)

    def test_name_too_long_rejected(self, valid):
        valid["name"] = "a" * 65
        assert_invalid(SCHEMA, valid)

    def test_name_max_length_valid(self, valid):
        valid["name"] = "a" * 64
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# last_restart_at oneOf(string|null)
# ---------------------------------------------------------------------------

class TestLastRestartAt:
    def test_valid_datetime_string(self, valid):
        valid["last_restart_at"] = "2026-01-15T11:58:30Z"
        assert_valid(SCHEMA, valid)

    def test_null_value(self, valid):
        valid["last_restart_at"] = None
        assert_valid(SCHEMA, valid)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_field_rejected(self, valid):
        valid["pid"] = 12345
        assert_invalid(SCHEMA, valid)

    def test_container_id_field_rejected(self, valid):
        valid["container_id"] = "abc123def456"
        assert_invalid(SCHEMA, valid)
