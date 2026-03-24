"""
Creative service HTTP API — ICD-5 manifest delivery.

Routes
------
GET /manifests/{manifest_id}
    Serve a single approved, non-expired manifest as JSON.
    200  — manifest JSON body
    403  — manifest exists but is not approved
    404  — manifest not found
    410  — manifest found and approved but expired

GET /manifests
    List all manifests (summary, includes approved/expired status).
    200  — JSON array of summary objects

GET /healthz   — liveness (always 200 if process alive)
GET /readyz    — readiness (200 when startup complete)

Design notes
------------
- The API is read-only for MVP. Manifest ingestion is via MANIFEST_DIR on disk.
  The dashboard-api is the canonical write authority (ICD-7).
- No authentication for MVP LAN deployment; WireGuard provides the network
  boundary (ICD-NET-1).
- Content-Type is always application/json.
"""
import json
import logging

from aiohttp import web

from .manifest_store import ManifestStore, NOT_FOUND, UNAPPROVED, EXPIRED

log = logging.getLogger(__name__)


def make_app(store: ManifestStore, is_ready: list) -> web.Application:
    app = web.Application()

    # ------------------------------------------------------------------
    # Manifest routes
    # ------------------------------------------------------------------

    async def get_manifest(request: web.Request) -> web.Response:
        manifest_id = request.match_info["manifest_id"]
        result = store.get(manifest_id)

        if isinstance(result, type(NOT_FOUND)):
            return web.Response(
                status=404,
                content_type="application/json",
                text=json.dumps({"error": "manifest_not_found", "manifest_id": manifest_id}),
            )
        if isinstance(result, type(UNAPPROVED)):
            return web.Response(
                status=403,
                content_type="application/json",
                text=json.dumps({"error": "manifest_not_approved", "manifest_id": manifest_id}),
            )
        if isinstance(result, type(EXPIRED)):
            return web.Response(
                status=410,
                content_type="application/json",
                text=json.dumps({"error": "manifest_expired", "manifest_id": manifest_id}),
            )

        log.debug("serving manifest: %s", manifest_id)
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(result),
        )

    async def list_manifests(request: web.Request) -> web.Response:
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(store.list_manifests()),
        )

    # ------------------------------------------------------------------
    # Health routes
    # ------------------------------------------------------------------

    async def healthz(request: web.Request) -> web.Response:
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok"}),
        )

    async def readyz(request: web.Request) -> web.Response:
        if not is_ready[0]:
            return web.Response(
                status=503,
                content_type="application/json",
                text=json.dumps({"status": "not_ready", "reason": "startup_in_progress"}),
            )
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({"status": "ok", **store.status()}),
        )

    app.router.add_get("/manifests/{manifest_id}", get_manifest)
    app.router.add_get("/manifests", list_manifests)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/readyz", readyz)

    return app
