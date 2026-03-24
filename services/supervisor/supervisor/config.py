"""
Supervisor service configuration — all values from environment variables.
Defaults target a docker-compose deployment on a single Jetson device.
"""
import os

# ── Polling intervals ──────────────────────────────────────────────────────

HEALTH_POLL_INTERVAL_S: float = float(
    os.environ.get("HEALTH_POLL_INTERVAL_S", "10")
)

SAFE_MODE_POLL_INTERVAL_S: float = float(
    os.environ.get("SAFE_MODE_POLL_INTERVAL_S", "15")
)

STORAGE_CHECK_INTERVAL_S: float = float(
    os.environ.get("STORAGE_CHECK_INTERVAL_S", "60")
)

# ── Restart-ladder thresholds ──────────────────────────────────────────────

# Restarts per service before the supervisor stops restarting and escalates.
RESTART_THRESHOLD: int = int(os.environ.get("RESTART_THRESHOLD", "5"))

# Window (seconds) used for boot-loop detection.
FAST_FAIL_WINDOW_S: float = float(os.environ.get("FAST_FAIL_WINDOW_S", "120"))

# Number of restarts within FAST_FAIL_WINDOW_S that triggers boot-loop mode.
BOOT_LOOP_THRESHOLD: int = int(os.environ.get("BOOT_LOOP_THRESHOLD", "3"))

# Minimum consecutive failures before a restart is attempted.
FAILURE_THRESHOLD: int = int(os.environ.get("FAILURE_THRESHOLD", "2"))

# ── Upstream service URLs ──────────────────────────────────────────────────

DASHBOARD_API_URL: str = os.environ.get(
    "DASHBOARD_API_URL", "http://dashboard-api:8000"
)

# Player health/control server (ICD-8 safe-mode relay endpoint).
PLAYER_CONTROL_URL: str = os.environ.get(
    "PLAYER_CONTROL_URL", "http://player:8080"
)

# Healthz URLs for each managed service.
PLAYER_HEALTHZ_URL: str = os.environ.get(
    "PLAYER_HEALTHZ_URL", "http://player:8080/healthz"
)
DECISION_OPTIMIZER_HEALTHZ_URL: str = os.environ.get(
    "DECISION_OPTIMIZER_HEALTHZ_URL", "http://decision-optimizer:8081/healthz"
)
AUDIENCE_STATE_HEALTHZ_URL: str = os.environ.get(
    "AUDIENCE_STATE_HEALTHZ_URL", "http://audience-state:8082/healthz"
)
CREATIVE_HEALTHZ_URL: str = os.environ.get(
    "CREATIVE_HEALTHZ_URL", "http://creative:8083/healthz"
)
DASHBOARD_API_HEALTHZ_URL: str = os.environ.get(
    "DASHBOARD_API_HEALTHZ_URL", "http://dashboard-api:8000/healthz"
)

# Docker container names to restart (must match docker-compose service names).
PLAYER_CONTAINER: str = os.environ.get("PLAYER_CONTAINER", "player")
DECISION_OPTIMIZER_CONTAINER: str = os.environ.get(
    "DECISION_OPTIMIZER_CONTAINER", "decision-optimizer"
)
AUDIENCE_STATE_CONTAINER: str = os.environ.get(
    "AUDIENCE_STATE_CONTAINER", "audience-state"
)
CREATIVE_CONTAINER: str = os.environ.get("CREATIVE_CONTAINER", "creative")
DASHBOARD_API_CONTAINER: str = os.environ.get(
    "DASHBOARD_API_CONTAINER", "dashboard-api"
)

# ── Infrastructure ─────────────────────────────────────────────────────────

# Set to "false" to disable docker restart calls (test / dev mode).
DOCKER_RESTART_ENABLED: bool = (
    os.environ.get("DOCKER_RESTART_ENABLED", "true").lower() == "true"
)

# Disk path to monitor for storage-full protection (REC-005).
STORAGE_DATA_PATH: str = os.environ.get("STORAGE_DATA_PATH", "/data")

# Percentage thresholds for storage alerts.
STORAGE_WARN_PCT: float = float(os.environ.get("STORAGE_WARN_PCT", "80"))
STORAGE_CRITICAL_PCT: float = float(os.environ.get("STORAGE_CRITICAL_PCT", "90"))

# Health server port for this supervisor service.
HEALTH_PORT: int = int(os.environ.get("HEALTH_PORT", "8090"))

# HTTP probe timeout (seconds).
PROBE_TIMEOUT_S: float = float(os.environ.get("PROBE_TIMEOUT_S", "5"))

# Log level (OBS-001).
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
