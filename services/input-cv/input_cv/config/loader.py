"""
Load and validate camera source configuration.

Two-phase validation:
1. jsonschema validates the raw dict against the authoritative JSON Schema.
2. Pydantic parses the validated dict into a typed CameraSourceConfig.

The JSON Schema path is resolved relative to the repo root so both the
live service and the test suite reference the single canonical schema.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import jsonschema.validators

from .settings import CameraSourceConfig

# Resolve the canonical schema from the contracts/ directory.
# This path is relative to the repo root, two levels above this service.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCHEMA_PATH = _REPO_ROOT / "contracts" / "input-cv" / "camera-source.schema.json"


class ConfigValidationError(ValueError):
    """Raised when the camera source config file fails schema or model validation."""


def _load_schema() -> dict:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Camera source schema not found at {_SCHEMA_PATH}. "
            "Ensure the repo root is correct and the contracts/ directory is present."
        )
    with _SCHEMA_PATH.open() as fh:
        return json.load(fh)


def load_camera_config(config_path: str | Path) -> CameraSourceConfig:
    """
    Load a camera source config file, validate it against the JSON Schema,
    and return a typed CameraSourceConfig.

    Raises:
        FileNotFoundError: if config_path or the schema file does not exist.
        ConfigValidationError: if the config fails schema or model validation.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Camera config not found: {path}")

    with path.open() as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(f"Config is not valid JSON: {exc}") from exc

    schema = _load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(raw), key=lambda e: e.path)
    if errors:
        messages = "; ".join(e.message for e in errors[:5])
        raise ConfigValidationError(f"Config failed JSON Schema validation: {messages}")

    try:
        return CameraSourceConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigValidationError(f"Config failed model validation: {exc}") from exc
