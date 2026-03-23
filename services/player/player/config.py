"""
Player service configuration — all values from environment variables.
Defaults are suitable for local development with stub renderer.
"""
import os
from pathlib import Path

# Decision-optimizer WebSocket endpoint (ICD-4)
DECISION_OPTIMIZER_WS_URL: str = os.environ.get(
    "DECISION_OPTIMIZER_WS_URL", "ws://localhost:8765/player/commands"
)

# Local directory where approved manifest JSON files are stored (ICD-5)
MANIFEST_STORE_PATH: str = os.environ.get("MANIFEST_STORE_PATH", "/data/manifests")

# Local directory where approved asset files are cached
ASSET_CACHE_PATH: str = os.environ.get("ASSET_CACHE_PATH", "/data/assets")

# Fallback bundle: directory and filename
FALLBACK_BUNDLE_PATH: str = os.environ.get(
    "FALLBACK_BUNDLE_PATH",
    str(Path(__file__).parent.parent / "fallback_bundle"),
)
FALLBACK_ASSET_NAME: str = os.environ.get("FALLBACK_ASSET_NAME", "fallback.jpg")

# Health server port (OBS-002)
HEALTH_PORT: int = int(os.environ.get("HEALTH_PORT", "8080"))

# Renderer backend: "stub" (no-op, for dev/test) or "mpv" (hardware)
RENDERER_BACKEND: str = os.environ.get("RENDERER_BACKEND", "stub")

# mpv IPC socket path (used by MpvRenderer)
MPV_IPC_SOCKET: str = os.environ.get("MPV_IPC_SOCKET", "/tmp/mpv-player.sock")

# WebSocket reconnect backoff (seconds)
WS_RECONNECT_INITIAL_BACKOFF_S: float = float(
    os.environ.get("WS_RECONNECT_INITIAL_BACKOFF_S", "1.0")
)
WS_RECONNECT_MAX_BACKOFF_S: float = float(
    os.environ.get("WS_RECONNECT_MAX_BACKOFF_S", "30.0")
)

# Directory containing ICD contract JSON schemas.
# Defaults to <repo-root>/contracts. Override in container with PLAYER_CONTRACT_DIR.
PLAYER_CONTRACT_DIR: str = os.environ.get(
    "PLAYER_CONTRACT_DIR",
    str(Path(__file__).parent.parent.parent.parent / "contracts"),
)

# Log level (OBS-001)
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
