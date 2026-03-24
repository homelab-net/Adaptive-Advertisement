"""
Unit tests for ManifestStore — manifest loading, validation, and serving.
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from creative.manifest_store import ManifestStore, NOT_FOUND, UNAPPROVED, EXPIRED
from tests.conftest import make_manifest, future_ts, past_ts, write_manifest


# ---------------------------------------------------------------------------
# load_manifest() — direct loading
# ---------------------------------------------------------------------------

class TestLoadManifest:
    def test_valid_approved_manifest_loads(self):
        store = ManifestStore()
        mid = store.load_manifest(make_manifest())
        assert mid == "test-manifest"

    def test_stored_after_load(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(manifest_id="m1"))
        result = store.get("m1")
        assert isinstance(result, dict)
        assert result["manifest_id"] == "m1"

    def test_schema_violation_raises(self):
        store = ManifestStore()
        bad = {"schema_version": "1.0.0"}  # missing required fields
        with pytest.raises(ValueError, match="schema"):
            store.load_manifest(bad)

    def test_wrong_schema_version_raises(self):
        store = ManifestStore()
        bad = make_manifest()
        bad["schema_version"] = "9.9.9"
        with pytest.raises(ValueError):
            store.load_manifest(bad)

    def test_unapproved_manifest_raises(self):
        store = ManifestStore()
        with pytest.raises(ValueError, match="approved"):
            store.load_manifest(make_manifest(approved=False))

    def test_unapproved_not_stored(self):
        store = ManifestStore()
        try:
            store.load_manifest(make_manifest(approved=False))
        except ValueError:
            pass
        assert store.get("test-manifest") is NOT_FOUND

    def test_manifest_with_expiry_in_future_loads(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=future_ts()))
        result = store.get("test-manifest")
        assert isinstance(result, dict)

    def test_manifest_with_expiry_in_past_loads_but_not_served(self):
        """Expired manifests are stored but refused at serve time."""
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=past_ts()))
        result = store.get("test-manifest")
        assert result is EXPIRED

    def test_multiple_items_manifest(self):
        store = ManifestStore()
        items = [
            {"item_id": "a", "asset_id": "a1", "asset_type": "video", "duration_ms": 5000},
            {"item_id": "b", "asset_id": "b1", "asset_type": "image", "duration_ms": 3000},
        ]
        store.load_manifest(make_manifest(items=items))
        result = store.get("test-manifest")
        assert isinstance(result, dict)
        assert len(result["items"]) == 2


# ---------------------------------------------------------------------------
# load_directory()
# ---------------------------------------------------------------------------

class TestLoadDirectory:
    def test_loads_all_json_files(self, manifest_dir):
        write_manifest(manifest_dir, make_manifest(manifest_id="m1"))
        write_manifest(manifest_dir, make_manifest(manifest_id="m2"))
        store = ManifestStore()
        count = store.load_directory(str(manifest_dir))
        assert count == 2

    def test_returns_zero_for_missing_dir(self):
        store = ManifestStore()
        count = store.load_directory("/no/such/directory")
        assert count == 0

    def test_skips_invalid_json(self, manifest_dir):
        (manifest_dir / "bad.json").write_text("not json {{{")
        store = ManifestStore()
        count = store.load_directory(str(manifest_dir))
        assert count == 0

    def test_skips_schema_violation(self, manifest_dir):
        (manifest_dir / "bad.json").write_text(json.dumps({"schema_version": "1.0.0"}))
        store = ManifestStore()
        count = store.load_directory(str(manifest_dir))
        assert count == 0

    def test_skips_unapproved_file(self, manifest_dir):
        write_manifest(manifest_dir, make_manifest(approved=False))
        store = ManifestStore()
        count = store.load_directory(str(manifest_dir))
        assert count == 0

    def test_loads_seed_manifests(self):
        """The committed seed manifests in services/creative/manifests/ must all load."""
        seed_dir = Path(__file__).parent.parent / "manifests"
        store = ManifestStore()
        count = store.load_directory(str(seed_dir))
        assert count == 3  # attract, default, group

    def test_load_errors_tracked(self, manifest_dir):
        (manifest_dir / "bad.json").write_text("invalid json")
        store = ManifestStore()
        store.load_directory(str(manifest_dir))
        assert store.status()["load_errors"] >= 1


# ---------------------------------------------------------------------------
# get() — serving logic
# ---------------------------------------------------------------------------

class TestGet:
    def test_returns_dict_for_valid_manifest(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(manifest_id="m"))
        assert isinstance(store.get("m"), dict)

    def test_returns_not_found_for_unknown_id(self):
        store = ManifestStore()
        assert store.get("no-such-id") is NOT_FOUND

    def test_returns_expired_when_past_expiry(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=past_ts()))
        assert store.get("test-manifest") is EXPIRED

    def test_returns_dict_when_not_expired(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=future_ts()))
        assert isinstance(store.get("test-manifest"), dict)

    def test_no_expiry_means_never_expires(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=None))
        assert isinstance(store.get("test-manifest"), dict)

    def test_expiry_clock_injectable(self):
        """Injectable clock: verify boundary at exactly expiry moment."""
        expiry = datetime(2030, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        store_before = ManifestStore(_now=lambda: expiry - timedelta(seconds=1))
        store_after  = ManifestStore(_now=lambda: expiry)

        manifest = make_manifest(expires_at="2030-06-01T12:00:00Z")
        store_before.load_manifest(manifest.copy())
        store_after.load_manifest(manifest.copy())

        assert isinstance(store_before.get("test-manifest"), dict)  # not yet expired
        assert store_after.get("test-manifest") is EXPIRED          # exactly at boundary


# ---------------------------------------------------------------------------
# list_manifests()
# ---------------------------------------------------------------------------

class TestListManifests:
    def test_empty_store_returns_empty_list(self):
        store = ManifestStore()
        assert store.list_manifests() == []

    def test_includes_all_stored_manifests(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(manifest_id="a"))
        store.load_manifest(make_manifest(manifest_id="b"))
        listing = store.list_manifests()
        ids = {m["manifest_id"] for m in listing}
        assert ids == {"a", "b"}

    def test_listing_sorted_by_manifest_id(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(manifest_id="z"))
        store.load_manifest(make_manifest(manifest_id="a"))
        ids = [m["manifest_id"] for m in store.list_manifests()]
        assert ids == sorted(ids)

    def test_listing_shows_expired_status(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(expires_at=past_ts()))
        listing = store.list_manifests()
        assert listing[0]["expired"] is True

    def test_listing_shows_item_count(self):
        store = ManifestStore()
        items = [
            {"item_id": "x", "asset_id": "a", "asset_type": "image", "duration_ms": 5000},
            {"item_id": "y", "asset_id": "b", "asset_type": "image", "duration_ms": 5000},
        ]
        store.load_manifest(make_manifest(items=items))
        assert store.list_manifests()[0]["item_count"] == 2


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------

class TestStatus:
    def test_status_counts_approved_active(self):
        store = ManifestStore()
        store.load_manifest(make_manifest(manifest_id="a"))
        store.load_manifest(make_manifest(manifest_id="b", expires_at=past_ts()))
        s = store.status()
        assert s["total_stored"] == 2
        assert s["approved_active"] == 1  # only non-expired counts

    def test_load_errors_in_status(self, manifest_dir):
        (manifest_dir / "bad.json").write_text("not json")
        store = ManifestStore()
        store.load_directory(str(manifest_dir))
        assert store.status()["load_errors"] >= 1
