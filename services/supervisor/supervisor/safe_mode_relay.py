"""
Safe-mode relay (ICD-8).

Polls dashboard-api for the operator safe-mode intent, then relays
engage / clear to the player via the player's /control/safe-mode HTTP
endpoint.

The relay is one-way: dashboard-api is the authoritative source of intent;
the player's control endpoint is the actuator. The supervisor bridges them.

State tracking
--------------
_engaged_by_dashboard tracks whether the relay has already sent an engage
command for the current dashboard intent.  This prevents redundant requests
on every poll tick.

_engaged_by_supervisor is set when the supervisor itself engages safe mode
due to a boot-loop or escalation event.  This is independent of the
dashboard intent.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

_SAFE_MODE_ENDPOINT = "/api/v1/safe-mode"
_PLAYER_SAFE_MODE_ENDPOINT = "/control/safe-mode"


class SafeModeRelay:
    def __init__(
        self,
        dashboard_api_url: str,
        player_control_url: str,
        poll_interval_s: float = 15.0,
    ) -> None:
        self._dashboard_url = dashboard_api_url.rstrip("/")
        self._player_url = player_control_url.rstrip("/")
        self._poll_interval = poll_interval_s
        self._engaged_by_dashboard: bool = False
        self._engaged_by_supervisor: bool = False

    # ── Public API ────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Poll dashboard-api and relay safe-mode changes to player. Runs forever."""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    await self._tick(session)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("safe-mode relay tick error: %s", exc)
                await asyncio.sleep(self._poll_interval)

    async def engage_safe_mode_supervisor(
        self,
        session: Optional[aiohttp.ClientSession],
        reason: str = "supervisor_escalation",
    ) -> bool:
        """
        Supervisor-initiated safe-mode (boot-loop / escalation).
        Sends POST /control/safe-mode to player regardless of dashboard state.
        Returns True on success.
        """
        async with aiohttp.ClientSession() as sess:
            s = session or sess
            ok = await self._post_engage(s, reason)
        if ok:
            self._engaged_by_supervisor = True
        return ok

    @property
    def is_safe_mode_active(self) -> bool:
        return self._engaged_by_dashboard or self._engaged_by_supervisor

    # ── Private ───────────────────────────────────────────────────────────

    async def _tick(self, session: aiohttp.ClientSession) -> None:
        intent = await self._poll_dashboard(session)
        if intent is None:
            # Dashboard API unreachable — leave current state unchanged.
            return

        dashboard_wants_safe_mode: bool = intent.get("is_active", False)
        reason: str = intent.get("reason") or "operator_manual"

        if dashboard_wants_safe_mode and not self._engaged_by_dashboard:
            ok = await self._post_engage(session, reason)
            if ok:
                self._engaged_by_dashboard = True
                log.info(
                    "safe mode engaged from dashboard reason=%s", reason
                )

        elif not dashboard_wants_safe_mode and self._engaged_by_dashboard:
            ok = await self._delete_clear(session)
            if ok:
                self._engaged_by_dashboard = False
                log.info("safe mode cleared from dashboard")

    async def _poll_dashboard(
        self, session: aiohttp.ClientSession
    ) -> Optional[dict]:
        url = f"{self._dashboard_url}{_SAFE_MODE_ENDPOINT}"
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                log.warning(
                    "dashboard safe-mode poll returned status=%d", resp.status
                )
                return None
        except Exception as exc:
            log.debug("dashboard safe-mode poll failed: %s", exc)
            return None

    async def _post_engage(
        self, session: aiohttp.ClientSession, reason: str
    ) -> bool:
        url = f"{self._player_url}{_PLAYER_SAFE_MODE_ENDPOINT}"
        try:
            async with session.post(
                url,
                json={"reason": reason},
                timeout=aiohttp.ClientTimeout(total=5.0),
            ) as resp:
                if resp.status == 200:
                    return True
                log.warning(
                    "player safe-mode engage returned status=%d", resp.status
                )
                return False
        except Exception as exc:
            log.warning("player safe-mode engage failed: %s", exc)
            return False

    async def _delete_clear(self, session: aiohttp.ClientSession) -> bool:
        url = f"{self._player_url}{_PLAYER_SAFE_MODE_ENDPOINT}"
        try:
            async with session.delete(
                url, timeout=aiohttp.ClientTimeout(total=5.0)
            ) as resp:
                if resp.status == 200:
                    return True
                log.warning(
                    "player safe-mode clear returned status=%d", resp.status
                )
                return False
        except Exception as exc:
            log.warning("player safe-mode clear failed: %s", exc)
            return False
