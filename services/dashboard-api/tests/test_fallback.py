"""
Tests for the fallback asset management router.

GET  /api/v1/fallback-assets           — list library contents
POST /api/v1/fallback-assets/activate  — write _selected marker
DELETE /api/v1/fallback-assets/selection — clear _selected marker

Uses the shared `client` fixture (in-memory SQLite, no PostgreSQL required).
Filesystem operations are patched to a tmp_path directory so no real volumes
are needed in CI.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio

# Override DB URL before any dashboard_api imports (matches conftest.py pattern)
os.environ.setdefault("DASHBOARD_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_asset(lib: Path, name: str, content: bytes = b"fake") -> Path:
    p = lib / name
    p.write_bytes(content)
    return p


# ── List endpoint ─────────────────────────────────────────────────────────────

class TestListFallbackAssets:
    async def test_200_empty_library(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.get("/api/v1/fallback-assets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["assets"] == []
        assert body["selected"] is None

    async def test_lists_png_files(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "brand.png")
        _write_asset(tmp_path, "promo.jpg")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        names = {a["name"] for a in body["assets"]}
        assert "brand.png" in names
        assert "promo.jpg" in names

    async def test_excludes_reserved_files(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "brand.png")
        (tmp_path / "_selected").write_text("brand.png")
        (tmp_path / ".gitkeep").write_bytes(b"")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        names = {a["name"] for a in body["assets"]}
        assert "_selected" not in names
        assert ".gitkeep" not in names

    async def test_excludes_unsupported_extensions(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "brand.png")
        _write_asset(tmp_path, "document.pdf")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        names = {a["name"] for a in body["assets"]}
        assert "document.pdf" not in names
        assert "brand.png" in names

    async def test_selected_marker_reflected_in_is_active(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "active.png")
        _write_asset(tmp_path, "inactive.png")
        (tmp_path / "_selected").write_text("active.png")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        by_name = {a["name"]: a for a in body["assets"]}
        assert by_name["active.png"]["is_active"] is True
        assert by_name["inactive.png"]["is_active"] is False
        assert body["selected"] == "active.png"

    async def test_asset_type_image_for_png(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "banner.png")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        assert body["assets"][0]["asset_type"] == "image"

    async def test_asset_type_video_for_mp4(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "promo.mp4")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        assert body["assets"][0]["asset_type"] == "video"


# ── Activate endpoint ─────────────────────────────────────────────────────────

class TestActivateFallbackAsset:
    async def test_200_writes_selected_marker(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "brand.png")
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": "brand.png"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["selected"] == "brand.png"
        assert (tmp_path / "_selected").read_text() == "brand.png"

    async def test_404_for_missing_file(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": "does-not-exist.png"},
        )
        assert resp.status_code == 404

    async def test_400_for_path_traversal(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": "../etc/passwd"},
        )
        assert resp.status_code == 400

    async def test_400_for_backslash_traversal(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": "..\\etc\\passwd"},
        )
        assert resp.status_code == 400

    async def test_400_for_dot_prefixed_name(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": ".hidden"},
        )
        assert resp.status_code == 400

    async def test_400_for_unsupported_extension(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "doc.pdf")
        resp = await client.post(
            "/api/v1/fallback-assets/activate",
            json={"name": "doc.pdf"},
        )
        assert resp.status_code == 400

    async def test_activate_updates_is_active_in_list(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "a.png")
        _write_asset(tmp_path, "b.png")
        await client.post(
            "/api/v1/fallback-assets/activate", json={"name": "a.png"}
        )
        resp = await client.get("/api/v1/fallback-assets")
        by_name = {a["name"]: a for a in resp.json()["assets"]}
        assert by_name["a.png"]["is_active"] is True
        assert by_name["b.png"]["is_active"] is False


# ── Clear selection endpoint ──────────────────────────────────────────────────

class TestClearFallbackSelection:
    async def test_200_removes_marker(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        (tmp_path / "_selected").write_text("brand.png")
        resp = await client.delete("/api/v1/fallback-assets/selection")
        assert resp.status_code == 200
        body = resp.json()
        assert body["selected"] is None
        assert not (tmp_path / "_selected").exists()

    async def test_200_when_no_marker_exists(self, client, tmp_path, monkeypatch):
        """Clearing when no marker is present must succeed idempotently."""
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        resp = await client.delete("/api/v1/fallback-assets/selection")
        assert resp.status_code == 200
        assert resp.json()["selected"] is None

    async def test_after_clear_list_shows_no_active(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard_api.routers.fallback.settings",
            type("S", (), {"fallback_library_dir": str(tmp_path)})(),
        )
        _write_asset(tmp_path, "brand.png")
        (tmp_path / "_selected").write_text("brand.png")
        await client.delete("/api/v1/fallback-assets/selection")
        resp = await client.get("/api/v1/fallback-assets")
        body = resp.json()
        assert body["selected"] is None
        assert all(not a["is_active"] for a in body["assets"])


# ── /metrics (OBS-003) via dashboard-api health router ───────────────────────

class TestDashboardApiMetrics:
    async def test_metrics_200(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200

    async def test_metrics_content_type_prometheus(self, client):
        resp = await client.get("/metrics")
        ct = resp.headers["content-type"]
        assert "text/plain" in ct

    async def test_metrics_body_has_help_lines(self, client):
        resp = await client.get("/metrics")
        assert "# HELP" in resp.text

    async def test_metrics_body_has_type_lines(self, client):
        resp = await client.get("/metrics")
        assert "# TYPE" in resp.text
