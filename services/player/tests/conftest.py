"""
Shared test fixtures for the player service test suite.

pytest-asyncio is configured with asyncio_mode = "auto" in pyproject.toml,
so async test functions are automatically treated as asyncio coroutines.
"""
import json
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared manifest fixture data
# ---------------------------------------------------------------------------

VALID_MANIFEST: dict = {
    "schema_version": "1.0.0",
    "manifest_id": "manifest-1",
    "approved_at": "2026-01-01T00:00:00Z",
    "approved_by": "operator-1",
    "items": [
        {
            "item_id": "item-1",
            "asset_id": "asset-1.jpg",
            "asset_type": "image",
            "duration_ms": 5000,
        }
    ],
}


@pytest.fixture()
def valid_manifest() -> dict:
    """Return a deep copy so individual tests cannot mutate the shared fixture."""
    import copy
    return copy.deepcopy(VALID_MANIFEST)


@pytest.fixture()
def manifest_dir(tmp_path: Path) -> Path:
    """Temporary directory pre-populated with one valid manifest JSON file."""
    (tmp_path / "manifest-1.json").write_text(json.dumps(VALID_MANIFEST))
    return tmp_path
