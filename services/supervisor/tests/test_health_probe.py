"""Tests for health_probe.probe()."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiohttp import ClientConnectorError, ServerTimeoutError

from supervisor.health_probe import probe, ProbeResult


class _MockResponse:
    def __init__(self, status: int):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class _MockSession:
    def __init__(self, response):
        self._response = response

    def get(self, url, **kwargs):
        return self._response


@pytest.mark.asyncio
async def test_healthy_200():
    session = _MockSession(_MockResponse(200))
    result = await probe(session, "player", "http://player/healthz")
    assert result.healthy is True
    assert result.status_code == 200
    assert result.error is None
    assert result.name == "player"


@pytest.mark.asyncio
async def test_healthy_503_readyz():
    """503 from /healthz is still < 500? No — 503 >= 500? No, 503 > 500 → unhealthy.
    But /healthz should never return 503; only /readyz does.
    Verify the threshold is < 500."""
    session = _MockSession(_MockResponse(503))
    result = await probe(session, "player", "http://player/healthz")
    assert result.healthy is False


@pytest.mark.asyncio
async def test_healthy_499():
    """4xx responses are considered healthy (service is responding)."""
    session = _MockSession(_MockResponse(404))
    result = await probe(session, "player", "http://player/healthz")
    assert result.healthy is True


@pytest.mark.asyncio
async def test_connection_error():
    class _FailSession:
        def get(self, url, **kwargs):
            return _FailContext()

    class _FailContext:
        async def __aenter__(self):
            # Raise a generic OSError so we exercise the unexpected-exception path
            # (ClientConnectorError constructor requires a real ConnectionKey).
            raise OSError("Connection refused")
        async def __aexit__(self, *_):
            pass

    result = await probe(_FailSession(), "player", "http://player/healthz")
    assert result.healthy is False
    assert result.status_code is None
    assert result.error is not None


@pytest.mark.asyncio
async def test_timeout_error():
    class _TimeoutSession:
        def get(self, url, **kwargs):
            return _TimeoutContext()

    class _TimeoutContext:
        async def __aenter__(self):
            raise ServerTimeoutError()
        async def __aexit__(self, *_):
            pass

    result = await probe(_TimeoutSession(), "player", "http://player/healthz")
    assert result.healthy is False
    assert "timeout" in result.error


@pytest.mark.asyncio
async def test_unexpected_exception():
    class _BrokenSession:
        def get(self, url, **kwargs):
            return _BrokenContext()

    class _BrokenContext:
        async def __aenter__(self):
            raise RuntimeError("unexpected")
        async def __aexit__(self, *_):
            pass

    result = await probe(_BrokenSession(), "player", "http://player/healthz")
    assert result.healthy is False
    assert "error" in result.error
