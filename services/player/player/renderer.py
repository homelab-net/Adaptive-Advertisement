"""
Renderer interface and implementations.

The renderer is the only component that drives the display. All other modules
describe what should be shown; this module makes it happen.

Never-blank contract
--------------------
show_fallback() must never silently fail. If the renderer cannot display the
fallback asset, it must raise RendererError so the caller can escalate.

Implementations
---------------
StubRenderer   — no-op, logs calls. Used for development and unit tests.
MpvRenderer    — drives mpv via its JSON IPC socket. Target for Jetson deployment.
                 At scaffold time the IPC wiring is complete but mpv is not
                 started automatically in CI; set RENDERER_BACKEND=mpv on device.

Factory
-------
create_renderer() reads RENDERER_BACKEND from config and returns the right instance.
"""
import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from . import config

log = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------

class RendererError(RuntimeError):
    """Raised when the renderer cannot fulfil a display request."""


class RendererStartupError(RendererError):
    """Raised by startup() when the renderer backend cannot be initialised."""


# ------------------------------------------------------------------
# Abstract base
# ------------------------------------------------------------------

class RendererBase(ABC):
    """Renderer interface. All methods are async."""

    @abstractmethod
    async def startup(self) -> None:
        """
        Initialise the renderer backend.
        Must be called once before any other method.
        Raises RendererStartupError on failure.
        """

    @abstractmethod
    async def show_fallback(self, asset_path: str) -> None:
        """
        Display the static fallback asset.
        Must succeed even if previous playback was degraded.
        Raises RendererError only on unrecoverable display failure.
        """

    @abstractmethod
    async def play_manifest_item(
        self,
        asset_path: str,
        asset_type: str,
        duration_ms: int,
        loop: bool = False,
    ) -> None:
        """
        Begin playing a single manifest item.
        asset_type: "video" | "image" | "html"
        duration_ms: target duration (advisory for video; mpv natural duration takes precedence)
        """

    @abstractmethod
    async def stop(self) -> None:
        """Cleanly stop the renderer (called on shutdown)."""


# ------------------------------------------------------------------
# Stub renderer (development / CI)
# ------------------------------------------------------------------

class StubRenderer(RendererBase):
    """
    No-op renderer that logs what would be displayed.
    Safe on any platform, no external dependencies.
    """

    async def startup(self) -> None:
        log.info("[stub-renderer] startup: ready")

    async def show_fallback(self, asset_path: str) -> None:
        log.info("[stub-renderer] show_fallback asset=%s", asset_path)

    async def play_manifest_item(
        self,
        asset_path: str,
        asset_type: str,
        duration_ms: int,
        loop: bool = False,
    ) -> None:
        log.info(
            "[stub-renderer] play type=%s asset=%s duration_ms=%d loop=%s",
            asset_type,
            asset_path,
            duration_ms,
            loop,
        )

    async def stop(self) -> None:
        log.info("[stub-renderer] stop")


# ------------------------------------------------------------------
# mpv renderer (Jetson deployment target)
# ------------------------------------------------------------------

class MpvRenderer(RendererBase):
    """
    Renderer backed by mpv using its JSON IPC socket protocol.

    Requires mpv ≥ 0.35 installed on the target system.
    The IPC socket path is configured via MPV_IPC_SOCKET.

    mpv is launched with:
      --idle=yes           — stay open with no file loaded
      --force-window=yes   — create a window even when idle
      --fullscreen=yes     — fill the display (Jetson kiosk mode)
      --no-terminal        — suppress terminal interaction
      --loop-file=inf      — default looping (overridden per item)

    Hardware note: GPU-accelerated decoding on Jetson Orin Nano uses nvdec.
    Pass --hwdec=nvdec-copy or --hwdec=cuda to mpv when bring-up confirms support.
    """

    _MPV_STARTUP_TIMEOUT_S = 5.0

    def __init__(self) -> None:
        self._process: Optional[asyncio.subprocess.Process] = None
        self._ipc_path = config.MPV_IPC_SOCKET

    async def startup(self) -> None:
        log.info("starting mpv IPC socket=%s", self._ipc_path)
        try:
            os.unlink(self._ipc_path)
        except FileNotFoundError:
            pass

        try:
            self._process = await asyncio.create_subprocess_exec(
                "mpv",
                "--idle=yes",
                "--force-window=yes",
                "--fullscreen=yes",
                "--no-terminal",
                f"--input-ipc-server={self._ipc_path}",
                "--loop-file=inf",
            )
        except FileNotFoundError:
            raise RendererStartupError(
                "mpv not found in PATH. "
                "Install mpv on the target device or set RENDERER_BACKEND=stub."
            )

        # Wait for IPC socket to appear
        deadline = asyncio.get_event_loop().time() + self._MPV_STARTUP_TIMEOUT_S
        while asyncio.get_event_loop().time() < deadline:
            if Path(self._ipc_path).exists():
                log.info("mpv ready ipc=%s", self._ipc_path)
                return
            await asyncio.sleep(0.1)

        raise RendererStartupError(
            f"mpv IPC socket did not appear within {self._MPV_STARTUP_TIMEOUT_S}s: "
            f"{self._ipc_path}"
        )

    async def show_fallback(self, asset_path: str) -> None:
        log.info("[mpv] show_fallback asset=%s", asset_path)
        await self._ipc(["loadfile", asset_path, "replace"])
        await self._ipc(["set_property", "loop-file", "inf"])

    async def play_manifest_item(
        self,
        asset_path: str,
        asset_type: str,
        duration_ms: int,
        loop: bool = False,
    ) -> None:
        log.info(
            "[mpv] play type=%s asset=%s duration_ms=%d loop=%s",
            asset_type,
            asset_path,
            duration_ms,
            loop,
        )
        await self._ipc(["loadfile", asset_path, "replace"])
        await self._ipc(
            ["set_property", "loop-file", "inf" if loop else "no"]
        )

    async def stop(self) -> None:
        if self._process is None:
            return
        log.info("[mpv] stopping")
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            log.warning("[mpv] terminate timed out — killing")
            self._process.kill()

    def _check_process_alive(self) -> None:
        """Raise RendererError if mpv has exited unexpectedly."""
        if self._process is not None and self._process.returncode is not None:
            raise RendererError(
                f"mpv process exited unexpectedly with code {self._process.returncode}"
            )

    async def _ipc(self, command: list) -> None:
        """Send a single JSON command to the mpv IPC socket."""
        self._check_process_alive()
        payload = json.dumps({"command": command}) + "\n"
        try:
            reader, writer = await asyncio.open_unix_connection(self._ipc_path)
            writer.write(payload.encode())
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except (OSError, ConnectionRefusedError) as exc:
            raise RendererError(f"mpv IPC send failed: {exc}") from exc


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def create_renderer() -> RendererBase:
    """Return the renderer selected by RENDERER_BACKEND config."""
    backend = config.RENDERER_BACKEND.lower()
    if backend == "mpv":
        log.info("renderer: mpv")
        return MpvRenderer()
    if backend != "stub":
        log.warning("unknown RENDERER_BACKEND=%r — falling back to stub", backend)
    log.info("renderer: stub")
    return StubRenderer()
