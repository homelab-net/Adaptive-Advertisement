"""
Unit tests for ManifestStore — ICD-5 approval enforcement.

Coverage targets
----------------
- Valid manifests are stored and retrievable
- Schema violations are rejected at put() time
- Missing approved_at / approved_by is caught by check_manifest()
- Expired manifests are rejected by check_manifest()
- Future expires_at passes check_manifest()
- No expires_at field passes check_manifest()
- load_from_disk() loads valid files, skips invalid, handles missing directory
"""
import json
import copy
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import player.config as cfg
from player.manifest_store import ManifestStore
from tests.conftest import VALID_MANIFEST


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store() -> ManifestStore:
    return ManifestStore()


@pytest.fixture()
def populated_store(store: ManifestStore) -> ManifestStore:
    store.put(copy.deepcopy(VALID_MANIFEST))
    return store


# ---------------------------------------------------------------------------
# put() and get()
# ---------------------------------------------------------------------------

class TestPutGet:
    def test_put_valid_manifest_succeeds(self, store):
        err = store.put(copy.deepcopy(VALID_MANIFEST))
        assert err is None

    def test_put_valid_manifest_is_retrievable(self, store):
        store.put(copy.deepcopy(VALID_MANIFEST))
        assert store.get("manifest-1") is not None

    def test_get_unknown_id_returns_none(self, store):
        assert store.get("no-such-manifest") is None

    def test_put_overrides_existing(self, store):
        m = copy.deepcopy(VALID_MANIFEST)
        store.put(m)
        m2 = copy.deepcopy(VALID_MANIFEST)
        m2["approved_by"] = "operator-2"
        store.put(m2)
        assert store.get("manifest-1")["approved_by"] == "operator-2"

    def test_put_schema_violation_rejected(self, store):
        bad = {"schema_version": "1.0.0", "manifest_id": "x"}  # missing items, etc.
        err = store.put(bad)
        assert err is not None
        assert store.get("x") is None

    def test_put_missing_approved_at_rejected(self, store):
        bad = copy.deepcopy(VALID_MANIFEST)
        del bad["approved_at"]
        err = store.put(bad)
        assert err is not None

    def test_put_missing_approved_by_rejected(self, store):
        bad = copy.deepcopy(VALID_MANIFEST)
        del bad["approved_by"]
        err = store.put(bad)
        assert err is not None

    def test_put_wrong_schema_version_rejected(self, store):
        bad = copy.deepcopy(VALID_MANIFEST)
        bad["schema_version"] = "9.9.9"
        err = store.put(bad)
        assert err is not None

    def test_put_empty_items_rejected(self, store):
        bad = copy.deepcopy(VALID_MANIFEST)
        bad["items"] = []  # minItems: 1
        err = store.put(bad)
        assert err is not None

    def test_manifest_ids_lists_stored(self, populated_store):
        assert "manifest-1" in populated_store.manifest_ids()


# ---------------------------------------------------------------------------
# check_manifest()
# ---------------------------------------------------------------------------

class TestCheckManifest:
    def test_valid_manifest_passes(self, populated_store):
        m = populated_store.get("manifest-1")
        assert populated_store.check_manifest(m) is None

    def test_no_expires_at_passes(self, populated_store):
        m = populated_store.get("manifest-1")
        assert "expires_at" not in m
        assert populated_store.check_manifest(m) is None

    def test_future_expires_at_passes(self, store):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        m = copy.deepcopy(VALID_MANIFEST)
        m["manifest_id"] = "future-m"
        m["expires_at"] = future
        store.put(m)
        assert store.check_manifest(store.get("future-m")) is None

    def test_past_expires_at_rejected(self, store):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        m = copy.deepcopy(VALID_MANIFEST)
        m["manifest_id"] = "expired-m"
        m["expires_at"] = past
        store.put(m)
        reason = store.check_manifest(store.get("expired-m"))
        assert reason is not None
        assert "expired" in reason

    def test_invalid_expires_at_format_rejected(self, store):
        m = copy.deepcopy(VALID_MANIFEST)
        m["manifest_id"] = "bad-date-m"
        m["expires_at"] = "not-a-date"
        # Schema does not strictly validate format at schema level (format is advisory);
        # check_manifest() catches the ValueError from fromisoformat
        store._manifests["bad-date-m"] = m  # bypass schema put()
        reason = store.check_manifest(m)
        assert reason is not None


# ---------------------------------------------------------------------------
# load_from_disk()
# ---------------------------------------------------------------------------

class TestLoadFromDisk:
    def test_load_from_missing_directory_returns_zero(self, store, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(tmp_path / "nonexistent"))
        assert store.load_from_disk() == 0

    def test_load_from_empty_directory_returns_zero(self, store, tmp_path, monkeypatch):
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(tmp_path))
        assert store.load_from_disk() == 0

    def test_load_valid_manifest_file(self, store, manifest_dir, monkeypatch):
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(manifest_dir))
        count = store.load_from_disk()
        assert count == 1
        assert store.get("manifest-1") is not None

    def test_load_skips_invalid_json(self, store, tmp_path, monkeypatch):
        (tmp_path / "garbage.json").write_text("not json {{{")
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(tmp_path))
        assert store.load_from_disk() == 0

    def test_load_skips_schema_invalid_manifests(self, store, tmp_path, monkeypatch):
        bad = {"schema_version": "1.0.0", "manifest_id": "bad"}
        (tmp_path / "bad.json").write_text(json.dumps(bad))
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(tmp_path))
        assert store.load_from_disk() == 0
        assert store.get("bad") is None

    def test_load_multiple_manifests(self, store, tmp_path, monkeypatch):
        for i in range(3):
            m = copy.deepcopy(VALID_MANIFEST)
            m["manifest_id"] = f"manifest-{i}"
            (tmp_path / f"manifest-{i}.json").write_text(json.dumps(m))
        monkeypatch.setattr(cfg, "MANIFEST_STORE_PATH", str(tmp_path))
        assert store.load_from_disk() == 3
