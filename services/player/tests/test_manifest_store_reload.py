"""
Unit tests for ManifestStore.reload() — full-replace semantics.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from player.manifest_store import ManifestStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_manifest(path: Path, manifest_id: str) -> None:
    manifest = {
        "schema_version": "1.0.0",
        "manifest_id": manifest_id,
        "approved_at": "2026-01-01T00:00:00Z",
        "approved_by": "operator",
        "items": [
            {
                "item_id": "item-001",
                "asset_id": "asset-001.png",
                "asset_type": "image",
                "duration_ms": 5000,
            }
        ],
    }
    (path / f"{manifest_id}.json").write_text(json.dumps(manifest))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestManifestStoreReload:

    def _store(self, store_path: Path) -> ManifestStore:
        """Create a ManifestStore pointing at store_path."""
        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
        return store

    def test_reload_picks_up_new_manifest(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()

        _write_manifest(store_path, "m-001")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            assert store.get("m-001") is not None
            assert store.get("m-002") is None

            # Add second manifest then reload
            _write_manifest(store_path, "m-002")
            count = store.reload()

        assert count == 2
        assert store.get("m-001") is not None
        assert store.get("m-002") is not None

    def test_reload_evicts_removed_manifest(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()

        _write_manifest(store_path, "m-001")
        _write_manifest(store_path, "m-002")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            assert store.get("m-001") is not None
            assert store.get("m-002") is not None

            # Remove m-002 from disk then reload
            (store_path / "m-002.json").unlink()
            count = store.reload()

        assert count == 1
        assert store.get("m-001") is not None
        assert store.get("m-002") is None

    def test_reload_no_changes(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()
        _write_manifest(store_path, "m-001")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            count = store.reload()

        assert count == 1
        assert store.get("m-001") is not None

    def test_reload_empty_dir_evicts_all(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()
        _write_manifest(store_path, "m-001")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            assert store.get("m-001") is not None

            # Remove all manifests
            (store_path / "m-001.json").unlink()
            count = store.reload()

        assert count == 0
        assert store.get("m-001") is None

    def test_reload_returns_correct_count(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()
        for i in range(5):
            _write_manifest(store_path, f"m-{i:03d}")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            count = store.reload()

        assert count == 5

    def test_reload_manifest_ids_updated(self, tmp_path):
        store_path = tmp_path / "manifests"
        store_path.mkdir()
        _write_manifest(store_path, "m-alpha")
        _write_manifest(store_path, "m-beta")

        with patch("player.config.MANIFEST_STORE_PATH", str(store_path)):
            store = ManifestStore()
            store.load_from_disk()
            assert set(store.manifest_ids()) == {"m-alpha", "m-beta"}

            (store_path / "m-alpha.json").unlink()
            _write_manifest(store_path, "m-gamma")
            store.reload()

        assert set(store.manifest_ids()) == {"m-beta", "m-gamma"}
