"""
Storage monitor — REC-005.

Checks disk usage on the data volume and logs warnings / critical alerts.
The supervisor loop calls check() periodically; no direct action is taken
beyond logging.  Future iterations could trigger cleanup or safe mode if
the disk is critically full.
"""
import shutil
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class StorageStatus:
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_pct: float
    warn_pct: float = 80.0
    critical_pct: float = 90.0

    @property
    def is_warning(self) -> bool:
        return self.used_pct >= self.warn_pct

    @property
    def is_critical(self) -> bool:
        return self.used_pct >= self.critical_pct

    @property
    def free_gb(self) -> float:
        return self.free_bytes / 1_000_000_000

    @property
    def total_gb(self) -> float:
        return self.total_bytes / 1_000_000_000


def check_storage(path: str, warn_pct: float = 80.0, critical_pct: float = 90.0) -> StorageStatus:
    """
    Check disk usage at path.

    Logs a warning if usage >= warn_pct, critical if >= critical_pct.
    Returns a StorageStatus regardless of outcome.
    Falls back to a zeroed status if shutil.disk_usage raises (e.g. path missing).
    """
    try:
        usage = shutil.disk_usage(path)
        used_pct = usage.used / usage.total * 100
        status = StorageStatus(
            path=path,
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            used_pct=used_pct,
            warn_pct=warn_pct,
            critical_pct=critical_pct,
        )
    except OSError as exc:
        log.error("storage check failed path=%s: %s", path, exc)
        return StorageStatus(
            path=path,
            total_bytes=0,
            used_bytes=0,
            free_bytes=0,
            used_pct=0.0,
            warn_pct=warn_pct,
            critical_pct=critical_pct,
        )

    if used_pct >= critical_pct:
        log.critical(
            "STORAGE CRITICAL path=%s used=%.1f%% free_gb=%.2f",
            path,
            used_pct,
            status.free_gb,
        )
    elif used_pct >= warn_pct:
        log.warning(
            "storage warning path=%s used=%.1f%% free_gb=%.2f",
            path,
            used_pct,
            status.free_gb,
        )
    else:
        log.debug(
            "storage ok path=%s used=%.1f%% free_gb=%.2f",
            path,
            used_pct,
            status.free_gb,
        )

    return status
