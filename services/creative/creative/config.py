"""
Creative service configuration — all values from environment variables.
"""
import os
from pathlib import Path

# Directory where manifest JSON files are stored
MANIFEST_DIR: str = os.environ.get(
    "MANIFEST_DIR",
    str(Path(__file__).parent.parent / "manifests"),
)

# HTTP server
HTTP_HOST: str = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT: int = int(os.environ.get("HTTP_PORT", "8090"))

# Health server (same port as HTTP for simplicity — both served by aiohttp)
HEALTH_PORT: int = HTTP_PORT

# Contract schema directory
CONTRACT_DIR: str = os.environ.get(
    "CONTRACT_DIR",
    str(Path(__file__).parent.parent.parent.parent / "contracts"),
)

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
