"""
HTTP API tests for the creative service.
Uses aiohttp's test client — no real HTTP server needed.
"""
import json
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from creative.manifest_store import ManifestStore
from creative.api import make_app
from tests.conftest import make_manifest, past_ts, future_ts


# ---------------------------------------------------------------------------
# Fixture: a test client with a pre-loaded store
# ---------------------------------------------------------------------------

@pytest.fixture()
async def client(aiohttp_client):
    store = ManifestStore()
    store.load_manifest(make_manifest(manifest_id="m-approved"))
    store.load_manifest(make_manifest(manifest_id="m-expired", expires_at=past_ts()))
    is_ready = [True]
    app = make_app(store, is_ready)
    return await aiohttp_client(app)


@pytest.fixture()
async def empty_client(aiohttp_client):
    store = ManifestStore()
    is_ready = [True]
    app = make_app(store, is_ready)
    return await aiohttp_client(app)


@pytest.fixture()
async def not_ready_client(aiohttp_client):
    store = ManifestStore()
    is_ready = [False]
    app = make_app(store, is_ready)
    return await aiohttp_client(app)


# ---------------------------------------------------------------------------
# GET /manifests/{manifest_id}
# ---------------------------------------------------------------------------

class TestGetManifest:
    async def test_200_for_approved_manifest(self, client):
        resp = await client.get("/manifests/m-approved")
        assert resp.status == 200

    async def test_body_is_valid_json_manifest(self, client):
        resp = await client.get("/manifests/m-approved")
        body = await resp.json()
        assert body["manifest_id"] == "m-approved"
        assert body["schema_version"] == "1.0.0"
        assert "items" in body

    async def test_content_type_json(self, client):
        resp = await client.get("/manifests/m-approved")
        assert "application/json" in resp.content_type

    async def test_404_for_unknown_manifest(self, client):
        resp = await client.get("/manifests/does-not-exist")
        assert resp.status == 404
        body = await resp.json()
        assert body["error"] == "manifest_not_found"

    async def test_410_for_expired_manifest(self, client):
        resp = await client.get("/manifests/m-expired")
        assert resp.status == 410
        body = await resp.json()
        assert body["error"] == "manifest_expired"

    async def test_404_body_includes_manifest_id(self, client):
        resp = await client.get("/manifests/unknown-id")
        body = await resp.json()
        assert body["manifest_id"] == "unknown-id"

    async def test_410_body_includes_manifest_id(self, client):
        resp = await client.get("/manifests/m-expired")
        body = await resp.json()
        assert body["manifest_id"] == "m-expired"


# ---------------------------------------------------------------------------
# GET /manifests
# ---------------------------------------------------------------------------

class TestListManifests:
    async def test_200_with_list(self, client):
        resp = await client.get("/manifests")
        assert resp.status == 200
        body = await resp.json()
        assert isinstance(body, list)

    async def test_includes_both_manifests(self, client):
        resp = await client.get("/manifests")
        body = await resp.json()
        ids = {m["manifest_id"] for m in body}
        assert "m-approved" in ids
        assert "m-expired" in ids

    async def test_expired_flagged_in_listing(self, client):
        resp = await client.get("/manifests")
        body = await resp.json()
        expired_entries = [m for m in body if m["manifest_id"] == "m-expired"]
        assert expired_entries[0]["expired"] is True

    async def test_empty_store_returns_empty_list(self, empty_client):
        resp = await empty_client.get("/manifests")
        assert resp.status == 200
        body = await resp.json()
        assert body == []


# ---------------------------------------------------------------------------
# GET /healthz
# ---------------------------------------------------------------------------

class TestHealthz:
    async def test_200_always(self, client):
        resp = await client.get("/healthz")
        assert resp.status == 200

    async def test_body_ok(self, client):
        body = await (await client.get("/healthz")).json()
        assert body["status"] == "ok"

    async def test_200_when_not_ready(self, not_ready_client):
        """Liveness check is independent of readiness."""
        resp = await not_ready_client.get("/healthz")
        assert resp.status == 200


# ---------------------------------------------------------------------------
# GET /readyz
# ---------------------------------------------------------------------------

class TestReadyz:
    async def test_200_when_ready(self, client):
        resp = await client.get("/readyz")
        assert resp.status == 200

    async def test_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/readyz")
        assert resp.status == 503

    async def test_readyz_includes_store_status(self, client):
        body = await (await client.get("/readyz")).json()
        assert "total_stored" in body
        assert "approved_active" in body
