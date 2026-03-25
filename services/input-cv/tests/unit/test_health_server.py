"""
Tests for input-cv health server — OBS-002, OBS-003.

Tests /healthz, /readyz, and /metrics endpoints via the aiohttp TestClient.
The HealthServer threading wrapper is tested separately with a real port probe.

Uses make_health_app() directly (no TCP listener needed) matching the pattern
in services/audience-state/tests/test_health_server.py.
"""
import asyncio
import json
import socket
import threading
import time

import pytest
from aiohttp.test_utils import TestClient, TestServer

from input_cv.health.server import make_health_app, HealthServer
from input_cv.health.tracker import HealthTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_tracker(ready: bool = True) -> tuple[HealthTracker, list]:
    tracker = HealthTracker(camera_id="cam-0", pipeline_id="pipeline-01")
    tracker.mark_device_present()
    tracker.mark_pipeline_running()
    tracker.record_frame()
    is_ready = [ready]
    return tracker, is_ready


@pytest.fixture
async def ready_client(aiohttp_client):
    tracker, is_ready = _make_tracker(ready=True)
    app = make_health_app(tracker, is_ready)
    return await aiohttp_client(app)


@pytest.fixture
async def not_ready_client(aiohttp_client):
    tracker, is_ready = _make_tracker(ready=False)
    app = make_health_app(tracker, is_ready)
    return await aiohttp_client(app)


# ---------------------------------------------------------------------------
# /healthz — liveness
# ---------------------------------------------------------------------------

class TestHealthz:
    async def test_200_always(self, ready_client):
        resp = await ready_client.get("/healthz")
        assert resp.status == 200

    async def test_body_status_ok(self, ready_client):
        body = await (await ready_client.get("/healthz")).json()
        assert body["status"] == "ok"

    async def test_200_when_not_ready(self, not_ready_client):
        """Liveness must be independent of readiness."""
        resp = await not_ready_client.get("/healthz")
        assert resp.status == 200

    async def test_content_type_json(self, ready_client):
        resp = await ready_client.get("/healthz")
        assert "application/json" in resp.content_type


# ---------------------------------------------------------------------------
# /readyz — readiness
# ---------------------------------------------------------------------------

class TestReadyz:
    async def test_200_when_ready(self, ready_client):
        resp = await ready_client.get("/readyz")
        assert resp.status == 200

    async def test_503_when_not_ready(self, not_ready_client):
        resp = await not_ready_client.get("/readyz")
        assert resp.status == 503

    async def test_readyz_body_has_status_ok(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert body["status"] == "ok"

    async def test_readyz_503_body_has_reason(self, not_ready_client):
        body = await (await not_ready_client.get("/readyz")).json()
        assert body["status"] == "not_ready"
        assert "reason" in body

    async def test_readyz_includes_health_fields(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert "camera_id" in body
        assert "pipeline_state" in body
        assert "device_present" in body

    async def test_readyz_device_present_true(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert body["device_present"] is True

    async def test_readyz_pipeline_state_running(self, ready_client):
        body = await (await ready_client.get("/readyz")).json()
        assert body["pipeline_state"] == "running"


# ---------------------------------------------------------------------------
# /metrics — OBS-003
# ---------------------------------------------------------------------------

class TestMetrics:
    async def test_200_response(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert resp.status == 200

    async def test_content_type_prometheus(self, ready_client):
        resp = await ready_client.get("/metrics")
        assert "text/plain" in resp.content_type

    async def test_body_has_help_lines(self, ready_client):
        text = await (await ready_client.get("/metrics")).text()
        assert "# HELP" in text

    async def test_body_has_type_lines(self, ready_client):
        text = await (await ready_client.get("/metrics")).text()
        assert "# TYPE" in text

    async def test_metrics_available_when_not_ready(self, not_ready_client):
        """/metrics must always be reachable regardless of readiness."""
        resp = await not_ready_client.get("/metrics")
        assert resp.status == 200


# ---------------------------------------------------------------------------
# HealthServer threading wrapper
# ---------------------------------------------------------------------------

class TestHealthServerThread:
    def _port_open(self, port: int, timeout: float = 0.1) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=timeout):
                return True
        except OSError:
            return False

    def _wait_for_port(self, port: int, retries: int = 20, delay: float = 0.1) -> bool:
        for _ in range(retries):
            if self._port_open(port):
                return True
            time.sleep(delay)
        return False

    def test_server_starts_and_binds(self):
        tracker = HealthTracker(camera_id="cam-test", pipeline_id="p-test")
        server = HealthServer(tracker, port=18906)
        server.start()
        assert self._wait_for_port(18906), "Health server did not bind within timeout"

    def test_mark_ready_before_start_is_false(self):
        tracker = HealthTracker(camera_id="cam-test2", pipeline_id="p-test2")
        server = HealthServer(tracker, port=18907)
        assert server._is_ready[0] is False

    def test_mark_ready_flips_flag(self):
        tracker = HealthTracker(camera_id="cam-test3", pipeline_id="p-test3")
        server = HealthServer(tracker, port=18908)
        server.start()
        self._wait_for_port(18908)
        server.mark_ready()
        assert server._is_ready[0] is True

    def test_thread_is_daemon(self):
        tracker = HealthTracker(camera_id="cam-test4", pipeline_id="p-test4")
        server = HealthServer(tracker, port=18909)
        server.start()
        assert server._thread is not None
        assert server._thread.daemon is True
