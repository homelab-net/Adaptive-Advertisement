"""
dashboard-api configuration.

All values come from environment variables (12-factor).
Defaults are safe for local development; production overrides via compose env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_", case_sensitive=False)

    # --- Database (ICD-7) -------------------------------------------------
    # PostgreSQL DSN for production. sqlite+aiosqlite:// URL works in tests.
    database_url: str = "postgresql+asyncpg://dashboard:dashboard@localhost:5432/dashboard"

    # --- Network ----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8004
    health_port: int = 8004  # health shares the main port on /healthz and /readyz

    # --- Service health probe URLs (ICD-6: GET /api/v1/status) -----------
    player_healthz_url: str = "http://player:8001/healthz"
    audience_state_healthz_url: str = "http://audience-state:8002/healthz"
    decision_optimizer_healthz_url: str = "http://decision-optimizer:8003/healthz"
    creative_healthz_url: str = "http://creative:8005/healthz"

    # Timeout for each downstream health probe (seconds)
    health_probe_timeout_s: float = 2.0

    # --- Filesystem -------------------------------------------------------
    # Directory where dashboard-api writes enabled manifests for creative service
    manifest_output_dir: str = "/data/manifests"

    # Asset storage root
    asset_storage_dir: str = "/data/assets"

    # Fallback asset library — shared volume with the player service.
    # Drop PNGs / MP4s here; write _selected to pin one without a restart.
    fallback_library_dir: str = "/data/fallback-library"

    # --- MQTT (ImpressionRecorder — ICD-3 + ICD-9) -----------------------
    # PLACEHOLDER: set DASHBOARD_MQTT_ENABLED=true once input-cv, audience-state,
    # and player ICD-9 event publisher are running on Jetson hardware.
    # Until then the ImpressionRecorder start() method is a no-op and all
    # analytics endpoints return data_available=False.
    mqtt_enabled: bool = False
    mqtt_broker_host: str = "mosquitto"
    mqtt_broker_port: int = 1883
    # Derived URL for logging
    @property
    def mqtt_broker_url(self) -> str:
        return f"mqtt://{self.mqtt_broker_host}:{self.mqtt_broker_port}"

    # --- Observability ---------------------------------------------------
    log_level: str = "INFO"

    # --- Pagination defaults ---------------------------------------------
    default_page_size: int = 20
    max_page_size: int = 100


settings = Settings()
