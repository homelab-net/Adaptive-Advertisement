"""
Shared fixtures for the creative service test suite.
"""
import json
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta


def make_manifest(
    manifest_id: str = "test-manifest",
    approved: bool = True,
    expires_at: str | None = None,
    items: list | None = None,
) -> dict:
    """Build a minimal valid ICD-5 creative manifest dict."""
    m: dict = {
        "schema_version": "1.0.0",
        "manifest_id": manifest_id,
        "items": items or [
            {
                "item_id": "item-01",
                "asset_id": "asset-01",
                "asset_type": "video",
                "duration_ms": 10000,
            }
        ],
    }
    if approved:
        m["approved_at"] = "2026-01-01T00:00:00Z"
        m["approved_by"] = "operator-01"
    if expires_at is not None:
        m["expires_at"] = expires_at
    return m


def future_ts(seconds: int = 3600) -> str:
    """RFC 3339 timestamp in the future."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def past_ts(seconds: int = 3600) -> str:
    """RFC 3339 timestamp in the past."""
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


@pytest.fixture()
def manifest_dir(tmp_path: Path) -> Path:
    """An empty temporary directory for manifest files."""
    return tmp_path


def write_manifest(directory: Path, manifest: dict) -> Path:
    """Write a manifest dict to a JSON file in the given directory."""
    path = directory / f"{manifest['manifest_id']}.json"
    path.write_text(json.dumps(manifest))
    return path
