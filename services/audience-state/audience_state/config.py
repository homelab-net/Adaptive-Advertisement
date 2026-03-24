"""
Audience-state service configuration — all values from environment variables.
"""
import os
from pathlib import Path

# MQTT broker
MQTT_BROKER_HOST: str = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT: int = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_CLIENT_ID: str = os.environ.get("MQTT_CLIENT_ID", "audience-state-01")
MQTT_RECONNECT_INITIAL_BACKOFF_S: float = float(
    os.environ.get("MQTT_RECONNECT_INITIAL_BACKOFF_S", "1.0")
)
MQTT_RECONNECT_MAX_BACKOFF_S: float = float(
    os.environ.get("MQTT_RECONNECT_MAX_BACKOFF_S", "30.0")
)

# ICD-2 inbound: cv-observation from input-cv
# Format: adaptive/v1/{tenant_id}/{site_id}/{camera_id}/cv-observation
MQTT_CV_OBSERVATION_TOPIC: str = os.environ.get(
    "MQTT_CV_OBSERVATION_TOPIC",
    "adaptive/v1/default-tenant/site-01/cam-01/cv-observation",
)

# ICD-3 outbound: audience-state-signal to decision-optimizer
# Format: adaptive/v1/{tenant_id}/{site_id}/audience-state
MQTT_AUDIENCE_STATE_TOPIC: str = os.environ.get(
    "MQTT_AUDIENCE_STATE_TOPIC",
    "adaptive/v1/default-tenant/site-01/audience-state",
)

# Identity fields used in outbound ICD-3 messages
TENANT_ID: str = os.environ.get("TENANT_ID", "default-tenant")
SITE_ID: str = os.environ.get("SITE_ID", "site-01")
CAMERA_ID: str = os.environ.get("CAMERA_ID", "cam-01")

# Smoothing window — observations older than this are discarded
WINDOW_MS: int = int(os.environ.get("WINDOW_MS", "5000"))

# Publish rate for ICD-3 signals (PERF-004 compatible: 1 Hz)
PUBLISH_HZ: float = float(os.environ.get("PUBLISH_HZ", "1.0"))

# Minimum observations required in window before state is considered stable
MIN_STABILITY_OBSERVATIONS: int = int(
    os.environ.get("MIN_STABILITY_OBSERVATIONS", "3")
)

# Confidence below this threshold → freeze_decision=True in outbound signal
CONFIDENCE_FREEZE_THRESHOLD: float = float(
    os.environ.get("CONFIDENCE_FREEZE_THRESHOLD", "0.5")
)

# Health server port (distinct from decision-optimizer's 8081)
HEALTH_PORT: int = int(os.environ.get("HEALTH_PORT", "8082"))

# Contract schema directory
CONTRACT_DIR: str = os.environ.get(
    "CONTRACT_DIR",
    str(Path(__file__).parent.parent.parent.parent / "contracts"),
)

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
