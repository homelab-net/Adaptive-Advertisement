"""
Managed service definitions and per-service runtime state.

ManagedService is static configuration (name, urls, container).
ServiceState is mutable runtime state tracking health and restart history.
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional

from . import config


# ── Service definition ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class ManagedService:
    """Static configuration for one managed service."""
    name: str
    healthz_url: str
    container_name: str
    # Priority determines whether a failure triggers safe-mode escalation.
    # "critical" → safe mode on boot-loop/escalation
    # "high"     → log escalation; safe mode if player is also degraded
    # "medium"   → log only
    priority: str


# ── Per-service runtime state ──────────────────────────────────────────────

@dataclass
class ServiceState:
    """Mutable runtime state tracked by the supervisor per managed service."""
    name: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    restart_count: int = 0
    # Monotonic timestamps of restart attempts (used for boot-loop detection).
    restart_timestamps: List[float] = field(default_factory=list)
    last_restart_at: Optional[float] = None
    in_boot_loop: bool = False
    escalated: bool = False

    def record_healthy(self) -> None:
        self.is_healthy = True
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        self.is_healthy = False
        self.consecutive_failures += 1

    def record_restart(self, now: Optional[float] = None) -> None:
        ts = now if now is not None else time.monotonic()
        self.restart_count += 1
        self.restart_timestamps.append(ts)
        self.last_restart_at = ts

    def prune_timestamps(self, window_s: float, now: Optional[float] = None) -> None:
        """Remove restart timestamps older than window_s."""
        cutoff = (now if now is not None else time.monotonic()) - window_s
        self.restart_timestamps = [t for t in self.restart_timestamps if t >= cutoff]


# ── Default service table ──────────────────────────────────────────────────

def build_service_table() -> List[ManagedService]:
    """Build the list of managed services from config."""
    return [
        ManagedService(
            name="player",
            healthz_url=config.PLAYER_HEALTHZ_URL,
            container_name=config.PLAYER_CONTAINER,
            priority="critical",
        ),
        ManagedService(
            name="decision-optimizer",
            healthz_url=config.DECISION_OPTIMIZER_HEALTHZ_URL,
            container_name=config.DECISION_OPTIMIZER_CONTAINER,
            priority="high",
        ),
        ManagedService(
            name="audience-state",
            healthz_url=config.AUDIENCE_STATE_HEALTHZ_URL,
            container_name=config.AUDIENCE_STATE_CONTAINER,
            priority="high",
        ),
        ManagedService(
            name="creative",
            healthz_url=config.CREATIVE_HEALTHZ_URL,
            container_name=config.CREATIVE_CONTAINER,
            priority="medium",
        ),
        ManagedService(
            name="dashboard-api",
            healthz_url=config.DASHBOARD_API_HEALTHZ_URL,
            container_name=config.DASHBOARD_API_CONTAINER,
            priority="medium",
        ),
    ]
