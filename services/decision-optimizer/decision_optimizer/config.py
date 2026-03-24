"""
Decision-optimizer service configuration — all values from environment variables.
"""
import os
from pathlib import Path

# MQTT broker (Eclipse Mosquitto 2.x, on-device sidecar)
MQTT_BROKER_HOST: str = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT: int = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
# Topic the audience-state service publishes to (ICD-3)
MQTT_AUDIENCE_STATE_TOPIC: str = os.environ.get(
    "MQTT_AUDIENCE_STATE_TOPIC", "adaptive/v1/default-tenant/site-01/audience-state"
)
MQTT_CLIENT_ID: str = os.environ.get("MQTT_CLIENT_ID", "decision-optimizer-01")
MQTT_RECONNECT_INITIAL_BACKOFF_S: float = float(
    os.environ.get("MQTT_RECONNECT_INITIAL_BACKOFF_S", "1.0")
)
MQTT_RECONNECT_MAX_BACKOFF_S: float = float(
    os.environ.get("MQTT_RECONNECT_MAX_BACKOFF_S", "30.0")
)

# WebSocket server for ICD-4 player commands
PLAYER_WS_HOST: str = os.environ.get("PLAYER_WS_HOST", "0.0.0.0")
PLAYER_WS_PORT: int = int(os.environ.get("PLAYER_WS_PORT", "8765"))
PLAYER_WS_PATH: str = os.environ.get("PLAYER_WS_PATH", "/player/commands")

# Decision loop cadence (PERF-004: 1 Hz ±10%)
DECISION_LOOP_HZ: float = float(os.environ.get("DECISION_LOOP_HZ", "1.0"))

# Signal staleness threshold — freeze player if no fresh signal for this long
STALE_SIGNAL_THRESHOLD_MS: int = int(
    os.environ.get("STALE_SIGNAL_THRESHOLD_MS", "5000")
)

# Rules file — JSON policy config loaded at startup
RULES_FILE: str = os.environ.get(
    "RULES_FILE",
    str(Path(__file__).parent.parent / "rules" / "default-rules.json"),
)

# Health server port (OBS-002)
HEALTH_PORT: int = int(os.environ.get("HEALTH_PORT", "8081"))

# Contract schema directory
CONTRACT_DIR: str = os.environ.get(
    "CONTRACT_DIR",
    str(Path(__file__).parent.parent.parent.parent / "contracts"),
)

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
