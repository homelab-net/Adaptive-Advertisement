"""
ICD-4 contract tests — PlayerCommand (decision-optimizer → player, WebSocket).

Schema: contracts/player/player-command.schema.json  v1.0

Key invariants under test:
- command_type enum is the only permitted discriminator
- sequence_number is required (ordering enforcement is in the player, not schema)
- command_id is required (idempotency enforcement is in the player, not schema)
- activate_creative payload is well-formed when present
- No unknown command types accepted
"""
from __future__ import annotations

import pytest

from .conftest import assert_invalid, assert_valid, load_schema

SCHEMA = load_schema("player/player-command.schema.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def base() -> dict:
    """Minimal valid freeze command (no payload required for freeze)."""
    return {
        "schema_version": "1.0.0",
        "command_id": "cmd-001",
        "sequence_number": 1,
        "produced_at": "2026-01-15T12:00:00Z",
        "command_type": "freeze",
    }


@pytest.fixture()
def activate_cmd() -> dict:
    return {
        "schema_version": "1.0.0",
        "command_id": "cmd-activate-01",
        "sequence_number": 5,
        "produced_at": "2026-01-15T12:00:05Z",
        "command_type": "activate_creative",
        "activate_creative": {
            "manifest_id": "manifest-attract-01",
            "min_dwell_ms": 5000,
        },
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidCommands:
    def test_freeze_minimal(self, base):
        assert_valid(SCHEMA, base)

    def test_freeze_with_reason(self, base):
        base["freeze"] = {"reason": "cv_degraded"}
        assert_valid(SCHEMA, base)

    @pytest.mark.parametrize("reason", [
        "cv_degraded", "decision_degraded", "thermal_protection", "operator_override",
    ])
    def test_all_freeze_reasons(self, base, reason):
        base["freeze"] = {"reason": reason}
        assert_valid(SCHEMA, base)

    def test_safe_mode_minimal(self, base):
        base["command_type"] = "safe_mode"
        assert_valid(SCHEMA, base)

    @pytest.mark.parametrize("reason", [
        "supervisor_escalation", "operator_manual", "boot_loop_protection",
    ])
    def test_all_safe_mode_reasons(self, base, reason):
        base["command_type"] = "safe_mode"
        base["safe_mode"] = {"reason": reason}
        assert_valid(SCHEMA, base)

    def test_clear_safe_mode(self, base):
        base["command_type"] = "clear_safe_mode"
        assert_valid(SCHEMA, base)

    def test_activate_creative_minimal(self, activate_cmd):
        assert_valid(SCHEMA, activate_cmd)

    def test_activate_creative_full_payload(self, activate_cmd):
        activate_cmd["activate_creative"]["cooldown_ms"] = 10000
        activate_cmd["activate_creative"]["rationale"] = "group audience detected"
        assert_valid(SCHEMA, activate_cmd)

    def test_sequence_number_zero(self, base):
        base["sequence_number"] = 0
        assert_valid(SCHEMA, base)

    def test_high_sequence_number(self, base):
        base["sequence_number"] = 999999
        assert_valid(SCHEMA, base)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:
    @pytest.mark.parametrize("field", [
        "schema_version", "command_id", "sequence_number", "produced_at", "command_type",
    ])
    def test_missing_required_field_rejected(self, base, field):
        del base[field]
        assert_invalid(SCHEMA, base)

    def test_missing_activate_creative_manifest_id_rejected(self, activate_cmd):
        del activate_cmd["activate_creative"]["manifest_id"]
        assert_invalid(SCHEMA, activate_cmd)

    def test_missing_activate_creative_min_dwell_ms_rejected(self, activate_cmd):
        del activate_cmd["activate_creative"]["min_dwell_ms"]
        assert_invalid(SCHEMA, activate_cmd)


# ---------------------------------------------------------------------------
# command_type enum
# ---------------------------------------------------------------------------

class TestCommandTypeEnum:
    @pytest.mark.parametrize("cmd_type", [
        "activate_creative", "freeze", "safe_mode", "clear_safe_mode",
    ])
    def test_all_valid_command_types(self, base, cmd_type):
        base["command_type"] = cmd_type
        assert_valid(SCHEMA, base)

    @pytest.mark.parametrize("bad_type", [
        "unfreeze", "resume", "restart", "shutdown", "activate", "stop",
    ])
    def test_unknown_command_types_rejected(self, base, bad_type):
        base["command_type"] = bad_type
        assert_invalid(SCHEMA, bad_type)

    def test_empty_command_type_rejected(self, base):
        base["command_type"] = ""
        assert_invalid(SCHEMA, base)


# ---------------------------------------------------------------------------
# Schema version enforcement
# ---------------------------------------------------------------------------

class TestSchemaVersion:
    def test_wrong_version_rejected(self, base):
        base["schema_version"] = "2.0.0"
        assert_invalid(SCHEMA, base)


# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

class TestNumericBounds:
    def test_sequence_number_negative_rejected(self, base):
        base["sequence_number"] = -1
        assert_invalid(SCHEMA, base)

    def test_min_dwell_ms_negative_rejected(self, activate_cmd):
        activate_cmd["activate_creative"]["min_dwell_ms"] = -1
        assert_invalid(SCHEMA, activate_cmd)

    def test_cooldown_ms_negative_rejected(self, activate_cmd):
        activate_cmd["activate_creative"]["cooldown_ms"] = -1
        assert_invalid(SCHEMA, activate_cmd)


# ---------------------------------------------------------------------------
# additionalProperties
# ---------------------------------------------------------------------------

class TestAdditionalProperties:
    def test_unknown_top_level_field_rejected(self, base):
        base["priority"] = 10
        assert_invalid(SCHEMA, base)

    def test_unknown_activate_creative_field_rejected(self, activate_cmd):
        activate_cmd["activate_creative"]["force"] = True
        assert_invalid(SCHEMA, activate_cmd)

    def test_unknown_freeze_field_rejected(self, base):
        base["freeze"] = {"reason": "cv_degraded", "duration_ms": 5000}
        assert_invalid(SCHEMA, base)
