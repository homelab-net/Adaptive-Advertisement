"""
Manifest store — approved-manifest authority for ICD-5.

Responsibilities
----------------
- Validate every manifest against creative-manifest.schema.json at load time
- Enforce the approved-only rule: reject manifests without approved_at + approved_by
- Check expiration at serve time (expires_at, if present)
- Serve validated, approved, non-expired manifests by manifest_id
- Expose a summary list for the management API

Manifest lifecycle for MVP
---------------------------
Manifests are loaded from JSON files in MANIFEST_DIR at service startup.
In full production, the dashboard-api writes approved manifests to MANIFEST_DIR;
the creative service hot-reloads on directory change (future work).
For MVP, a restart loads any new manifests.

Approved-only invariant (from locked requirements)
----------------------------------------------------
A manifest is only served if:
  1. It was loaded and passed schema validation
  2. It has both approved_at and approved_by fields (non-empty)
  3. Its expires_at has not passed (if present)

A failed validation or missing approval fields → the manifest is logged and
skipped at load time, never stored. An expired manifest stays in the store
but is refused at serve time (410 Gone).

Testability
-----------
The _now callable is injectable so expiry tests need no real sleeps.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import jsonschema

from . import config

log = logging.getLogger(__name__)

_SCHEMA_PATH = (
    Path(config.CONTRACT_DIR) / "creative" / "creative-manifest.schema.json"
)


def _load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


# Sentinel values returned by get() to allow callers to distinguish cases
class _NotFound:
    pass


class _Unapproved:
    pass


class _Expired:
    pass


NOT_FOUND = _NotFound()
UNAPPROVED = _Unapproved()
EXPIRED = _Expired()


class ManifestStore:
    """
    In-memory manifest store loaded from the manifest directory.
    Thread-safe for reads from a single asyncio event loop.
    """

    def __init__(self, _now: Optional[Callable[[], datetime]] = None) -> None:
        schema = _load_schema()
        self._validator = jsonschema.Draft202012Validator(schema)
        self._manifests: dict[str, dict] = {}   # manifest_id → validated dict
        self._now: Callable[[], datetime] = _now or (
            lambda: datetime.now(timezone.utc)
        )
        self._load_errors: int = 0

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_directory(self, manifest_dir: str) -> int:
        """
        Load all *.json files from manifest_dir.
        Returns the count of successfully loaded manifests.
        Silently skips files that fail validation or are unapproved.
        """
        dir_path = Path(manifest_dir)
        if not dir_path.is_dir():
            log.warning("manifest directory not found: %s", dir_path)
            return 0

        loaded = 0
        for path in sorted(dir_path.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                self._store(data, source=path.name)
                loaded += 1
            except (json.JSONDecodeError, OSError) as exc:
                log.error("skipping %s: %s", path.name, exc)
                self._load_errors += 1
            except ValueError as exc:
                # _store() already incremented _load_errors
                log.error("skipping %s: %s", path.name, exc)

        log.info("loaded %d manifest(s) from %s", loaded, dir_path)
        return loaded

    def load_manifest(self, data: dict) -> str:
        """
        Validate and store a single manifest dict (e.g. from tests or API).
        Returns the manifest_id on success.
        Raises ValueError on schema failure or missing approval fields.
        """
        self._store(data, source="<direct>")
        return data["manifest_id"]

    # ------------------------------------------------------------------
    # Serve
    # ------------------------------------------------------------------

    def get(
        self, manifest_id: str
    ) -> "dict | _NotFound | _Unapproved | _Expired":
        """
        Return the manifest dict, or a sentinel explaining why it's unavailable.

        Callers should check:
            result is NOT_FOUND   → HTTP 404
            result is UNAPPROVED  → HTTP 403
            result is EXPIRED     → HTTP 410
            isinstance(result, dict) → HTTP 200
        """
        manifest = self._manifests.get(manifest_id)
        if manifest is None:
            return NOT_FOUND

        if not self._is_approved(manifest):
            return UNAPPROVED

        if self._is_expired(manifest):
            return EXPIRED

        return manifest

    def list_manifests(self) -> list[dict]:
        """
        Return a summary list of all stored manifests (including unapproved /
        expired, so operators can see everything).
        """
        now = self._now()
        result = []
        for m in self._manifests.values():
            approved = self._is_approved(m)
            expired = self._is_expired(m) if approved else False
            result.append({
                "manifest_id": m["manifest_id"],
                "approved": approved,
                "expired": expired,
                "item_count": len(m.get("items", [])),
                "approved_at": m.get("approved_at"),
                "expires_at": m.get("expires_at"),
            })
        return sorted(result, key=lambda x: x["manifest_id"])

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def status(self) -> dict:
        approved = sum(
            1 for m in self._manifests.values()
            if self._is_approved(m) and not self._is_expired(m)
        )
        return {
            "total_stored": len(self._manifests),
            "approved_active": approved,
            "load_errors": self._load_errors,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _store(self, data: dict, source: str) -> None:
        """Validate and store; raises ValueError on any failure."""
        errors = list(self._validator.iter_errors(data))
        if errors:
            msg = "; ".join(e.message for e in errors[:3])
            self._load_errors += 1
            raise ValueError(f"schema validation failed ({source}): {msg}")

        if not self._is_approved(data):
            self._load_errors += 1
            raise ValueError(
                f"manifest {data.get('manifest_id')!r} missing approved_at "
                f"or approved_by — not loaded ({source})"
            )

        manifest_id: str = data["manifest_id"]
        self._manifests[manifest_id] = data
        log.info(
            "manifest loaded: id=%s items=%d approved_by=%s source=%s",
            manifest_id,
            len(data.get("items", [])),
            data.get("approved_by"),
            source,
        )

    @staticmethod
    def _is_approved(manifest: dict) -> bool:
        return bool(
            manifest.get("approved_at") and manifest.get("approved_by")
        )

    def _is_expired(self, manifest: dict) -> bool:
        expires_at = manifest.get("expires_at")
        if not expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return self._now() >= expiry
        except ValueError:
            log.warning(
                "manifest %s: invalid expires_at=%r — treating as expired",
                manifest.get("manifest_id"),
                expires_at,
            )
            return True
