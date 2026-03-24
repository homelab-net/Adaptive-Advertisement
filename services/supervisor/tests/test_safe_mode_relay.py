"""Tests for SafeModeRelay."""
import pytest
from unittest.mock import AsyncMock, patch

from supervisor.safe_mode_relay import SafeModeRelay


# ── Minimal mock HTTP session ──────────────────────────────────────────────

class _Response:
    def __init__(self, status: int, json_data: dict | None = None):
        self.status = status
        self._data = json_data or {}

    async def json(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class _Session:
    """Records calls and returns configured responses."""
    def __init__(self):
        self.get_responses: list[_Response] = []
        self.post_called: list[dict] = []
        self.delete_called: int = 0
        self._post_response = _Response(200)
        self._delete_response = _Response(200)

    def get(self, url, **kwargs):
        if self.get_responses:
            return self.get_responses.pop(0)
        return _Response(200, {"is_active": False})

    def post(self, url, json=None, **kwargs):
        self.post_called.append({"url": url, "json": json})
        return self._post_response

    def delete(self, url, **kwargs):
        self.delete_called += 1
        return self._delete_response


def _relay(**kwargs) -> SafeModeRelay:
    return SafeModeRelay(
        dashboard_api_url="http://dashboard-api:8000",
        player_control_url="http://player:8080",
        poll_interval_s=kwargs.get("poll_interval_s", 15.0),
    )


# ── Tests ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_action_when_inactive():
    relay = _relay()
    session = _Session()
    session.get_responses = [_Response(200, {"is_active": False})]
    await relay._tick(session)
    assert not session.post_called
    assert session.delete_called == 0


@pytest.mark.asyncio
async def test_engages_when_dashboard_active():
    relay = _relay()
    session = _Session()
    session.get_responses = [_Response(200, {"is_active": True, "reason": "operator_manual"})]
    await relay._tick(session)
    assert len(session.post_called) == 1
    assert session.post_called[0]["json"]["reason"] == "operator_manual"
    assert relay._engaged_by_dashboard is True


@pytest.mark.asyncio
async def test_does_not_re_engage_if_already_engaged():
    relay = _relay()
    relay._engaged_by_dashboard = True  # already engaged
    session = _Session()
    session.get_responses = [_Response(200, {"is_active": True, "reason": "operator_manual"})]
    await relay._tick(session)
    assert not session.post_called  # no redundant POST


@pytest.mark.asyncio
async def test_clears_when_dashboard_inactive_and_was_engaged():
    relay = _relay()
    relay._engaged_by_dashboard = True  # was engaged
    session = _Session()
    session.get_responses = [_Response(200, {"is_active": False})]
    await relay._tick(session)
    assert session.delete_called == 1
    assert relay._engaged_by_dashboard is False


@pytest.mark.asyncio
async def test_no_clear_when_never_engaged():
    relay = _relay()
    session = _Session()
    session.get_responses = [_Response(200, {"is_active": False})]
    await relay._tick(session)
    assert session.delete_called == 0


@pytest.mark.asyncio
async def test_dashboard_unreachable_leaves_state_unchanged():
    relay = _relay()
    relay._engaged_by_dashboard = True

    class _BrokenSession:
        def get(self, url, **kwargs):
            return _BrokenContext()

    class _BrokenContext:
        async def __aenter__(self):
            raise OSError("connection refused")
        async def __aexit__(self, *_):
            pass

    await relay._tick(_BrokenSession())
    # State must not change when dashboard is unreachable.
    assert relay._engaged_by_dashboard is True


@pytest.mark.asyncio
async def test_dashboard_non_200_leaves_state_unchanged():
    relay = _relay()
    session = _Session()
    session.get_responses = [_Response(503)]
    await relay._tick(session)
    assert relay._engaged_by_dashboard is False
    assert not session.post_called


@pytest.mark.asyncio
async def test_engage_returns_true_on_success():
    relay = _relay()
    session = _Session()
    ok = await relay._post_engage(session, "supervisor_escalation")
    assert ok is True
    assert relay._engaged_by_dashboard is False  # _post_engage doesn't set the flag


@pytest.mark.asyncio
async def test_engage_returns_false_on_player_error():
    relay = _relay()

    class _FailSession:
        def post(self, url, **kwargs):
            return _BrokenContext()

    class _BrokenContext:
        async def __aenter__(self):
            raise OSError("refused")
        async def __aexit__(self, *_):
            pass

    ok = await relay._post_engage(_FailSession(), "operator_manual")
    assert ok is False


@pytest.mark.asyncio
async def test_is_safe_mode_active_property():
    relay = _relay()
    assert relay.is_safe_mode_active is False
    relay._engaged_by_dashboard = True
    assert relay.is_safe_mode_active is True
    relay._engaged_by_dashboard = False
    relay._engaged_by_supervisor = True
    assert relay.is_safe_mode_active is True
