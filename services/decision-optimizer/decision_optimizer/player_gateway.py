"""
Player gateway — ICD-4 WebSocket server.

The decision-optimizer is the WebSocket server; the player is the client.
This module accepts player connections and broadcasts commands.

Command dispatch
----------------
Commands are JSON objects conforming to player-command.schema.json.
Each command has a globally monotonic sequence_number and a unique command_id.
The sequence_number never resets — when a player reconnects it resets its own
session counter to -1, so any positive sequence will be accepted (per CRM-002).

Multi-connection
----------------
The MVP is a single-device appliance, so one player connection is the normal
case. The gateway handles multiple connections correctly (broadcast semantics)
for forward compatibility, but does not require them.

Send failures
-------------
If a send fails on one connection (disconnected mid-broadcast), it is removed
from the active set and the failure is logged. Other connections are unaffected.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

import websockets
import websockets.exceptions
import websockets.server

from . import config

log = logging.getLogger(__name__)


class PlayerGateway:
    def __init__(self) -> None:
        self._connections: Set[websockets.server.WebSocketServerProtocol] = set()
        self._sequence: int = 0
        self._server: Optional[websockets.server.WebSocketServer] = None

    # ------------------------------------------------------------------
    # Server lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server. Call once during startup."""
        self._server = await websockets.serve(
            self._handler,
            config.PLAYER_WS_HOST,
            config.PLAYER_WS_PORT,
            ping_interval=20,
            ping_timeout=10,
        )
        log.info(
            "player gateway listening ws://%s:%d%s",
            config.PLAYER_WS_HOST,
            config.PLAYER_WS_PORT,
            config.PLAYER_WS_PATH,
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            log.info("player gateway stopped")

    async def _handler(
        self, ws: websockets.server.WebSocketServerProtocol
    ) -> None:
        """Accept and hold a player connection until it closes."""
        remote = ws.remote_address
        log.info("player connected: %s", remote)
        self._connections.add(ws)
        try:
            await ws.wait_closed()
        finally:
            self._connections.discard(ws)
            log.info("player disconnected: %s", remote)

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def send_activate_creative(
        self,
        manifest_id: str,
        min_dwell_ms: int,
        cooldown_ms: int = 0,
        rationale: Optional[str] = None,
    ) -> int:
        """
        Broadcast an activate_creative command to all connected players.
        Returns the number of players the command was sent to.
        """
        payload: dict = {"manifest_id": manifest_id, "min_dwell_ms": min_dwell_ms}
        if cooldown_ms:
            payload["cooldown_ms"] = cooldown_ms
        if rationale:
            payload["rationale"] = rationale

        return await self._broadcast("activate_creative", payload)

    async def send_freeze(self, reason: Optional[str] = None) -> int:
        """
        Broadcast a freeze command to all connected players.
        Returns the number of players the command was sent to.
        """
        payload: dict = {}
        if reason:
            payload["reason"] = reason
        return await self._broadcast("freeze", payload if payload else None)

    async def send_safe_mode(self, reason: Optional[str] = None) -> int:
        """
        Broadcast a safe_mode command. Normally issued by the supervisor (ICD-8);
        exposed here so the decision-optimizer can escalate in extreme degradation.
        Returns the number of players the command was sent to.
        """
        payload: dict = {}
        if reason:
            payload["reason"] = reason
        return await self._broadcast("safe_mode", payload if payload else None)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def player_count(self) -> int:
        return len(self._connections)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _next_command(self, command_type: str, payload: Optional[dict]) -> str:
        self._sequence += 1
        msg: dict = {
            "schema_version": "1.0.0",
            "command_id": str(uuid.uuid4()),
            "sequence_number": self._sequence,
            "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "command_type": command_type,
        }
        if payload is not None:
            msg[command_type] = payload
        return json.dumps(msg)

    async def _broadcast(
        self, command_type: str, payload: Optional[dict]
    ) -> int:
        if not self._connections:
            log.debug("broadcast %s: no players connected", command_type)
            return 0

        raw = self._next_command(command_type, payload)
        log.info(
            "broadcast command: type=%s seq=%d players=%d",
            command_type,
            self._sequence,
            len(self._connections),
        )

        dead: Set[websockets.server.WebSocketServerProtocol] = set()
        sent = 0
        for ws in list(self._connections):
            try:
                await ws.send(raw)
                sent += 1
            except (
                websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException,
            ) as exc:
                log.warning("send failed to %s: %s — removing", ws.remote_address, exc)
                dead.add(ws)

        self._connections -= dead
        return sent
