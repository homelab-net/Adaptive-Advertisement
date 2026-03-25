"""
Shared helpers for contract tests.

Contract tests validate ICD schemas directly using jsonschema — no service
imports required. Tests confirm that:
  - Correct payloads are accepted
  - Invalid / incomplete payloads are rejected
  - Privacy-critical const:false fields are enforced
  - additionalProperties:false boundaries are enforced
  - Enum, pattern, min/max, and format constraints work as specified
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

_REPO = Path(__file__).resolve().parents[2]
_CONTRACTS = _REPO / "contracts"


def load_schema(rel_path: str) -> dict:
    """Load a JSON schema from the contracts/ directory."""
    return json.loads((_CONTRACTS / rel_path).read_text())


def validator_for(schema: dict) -> jsonschema.protocols.Validator:
    """Return a configured Draft202012Validator for *schema*."""
    return jsonschema.Draft202012Validator(schema)


def assert_valid(schema: dict, instance: Any) -> None:
    """Assert *instance* is valid against *schema*; raises AssertionError on failure."""
    v = validator_for(schema)
    errors = list(v.iter_errors(instance))
    assert not errors, f"Expected valid but got errors:\n" + "\n".join(
        f"  [{e.json_path}] {e.message}" for e in errors
    )


def assert_invalid(schema: dict, instance: Any) -> None:
    """Assert *instance* is invalid against *schema*; raises AssertionError if valid."""
    v = validator_for(schema)
    errors = list(v.iter_errors(instance))
    assert errors, "Expected invalid but schema accepted the instance"
