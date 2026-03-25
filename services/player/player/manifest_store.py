"""
Manifest store — local cache of approved creative manifests (ICD-5).

Manifests are loaded at startup from MANIFEST_STORE_PATH (JSON files) and can
be added at runtime via put(). Before any manifest is rendered, check_manifest()
enforces approval and expiry invariants.

Approval enforcement
--------------------
- approved_at and approved_by are required by the schema and double-checked here.
- expires_at, if present, is compared against wall-clock UTC.
- An unapproved or expired manifest is rejected; playback continues on current content.

No-blank guarantee
------------------
Rejection at this layer means the activate_creative command is dropped and the
state machine is not called — playback holds the current creative or fallback.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import jsonschema

from . import config

log = logging.getLogger(__name__)

_MANIFEST_SCHEMA_PATH = (
    Path(config.PLAYER_CONTRACT_DIR) / "creative" / "creative-manifest.schema.json"
)


def _load_manifest_schema() -> dict:
    with open(_MANIFEST_SCHEMA_PATH) as f:
        return json.load(f)


class ManifestStore:
    """
    In-memory manifest registry.

    All mutations (put, load_from_disk, reload) should be called from the single
    asyncio event loop thread; no explicit locking is used.
    """

    def __init__(self) -> None:
        self._manifests: dict[str, dict] = {}
        self._schema = _load_manifest_schema()
        self._validator = jsonschema.Draft202012Validator(self._schema)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def load_from_disk(self) -> int:
        """
        Load all *.json files from MANIFEST_STORE_PATH.
        Returns count of successfully loaded manifests.
        Missing or non-existent directory is treated as empty (not an error).
        """
        store_path = Path(config.MANIFEST_STORE_PATH)
        if not store_path.exists():
            log.info("manifest store path absent — starting with empty store: %s", store_path)
            return 0

        loaded = 0
        for manifest_file in sorted(store_path.glob("*.json")):
            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                log.error("manifest file unreadable: %s — %s", manifest_file.name, exc)
                continue

            err = self._validate_schema(manifest)
            if err:
                log.error(
                    "manifest file rejected (schema): %s — %s", manifest_file.name, err
                )
                continue

            manifest_id = manifest["manifest_id"]
            self._manifests[manifest_id] = manifest
            loaded += 1
            log.info("manifest loaded from disk: %s", manifest_id)

        log.info(
            "manifest store loaded %d manifest(s) from %s", loaded, store_path
        )
        return loaded

    def reload(self) -> int:
        """
        Full-replace rescan of MANIFEST_STORE_PATH.

        Clears all current manifests, then calls load_from_disk().
        Manifests removed from disk are evicted; manifests added to disk are
        ingested.  Returns the count of manifests after the reload.

        Use full-replace rather than merge so that disabling a manifest in
        the dashboard (which removes the file) takes effect on the next cycle.
        """
        old_ids = set(self._manifests.keys())
        self._manifests.clear()
        count = self.load_from_disk()
        new_ids = set(self._manifests.keys())

        evicted = old_ids - new_ids
        added = new_ids - old_ids
        if evicted:
            log.info("manifest reload: evicted %d manifest(s): %s", len(evicted), sorted(evicted))
        if added:
            log.info("manifest reload: added %d manifest(s): %s", len(added), sorted(added))
        if not evicted and not added:
            log.debug("manifest reload: no changes (count=%d)", count)

        return count

    def put(self, manifest: dict) -> Optional[str]:
        """
        Store a manifest received at runtime.
        Returns None on success, or an error string on rejection.
        """
        err = self._validate_schema(manifest)
        if err:
            return f"schema:{err}"
        manifest_id = manifest["manifest_id"]
        self._manifests[manifest_id] = manifest
        log.info("manifest stored: %s", manifest_id)
        return None

    # ------------------------------------------------------------------
    # Lookup and enforcement
    # ------------------------------------------------------------------

    def get(self, manifest_id: str) -> Optional[dict]:
        """Return manifest dict or None if not known."""
        return self._manifests.get(manifest_id)

    def check_manifest(self, manifest: dict) -> Optional[str]:
        """
        Verify a manifest is safe to render right now.
        Returns None if OK, or a rejection reason string.

        Checks (beyond schema, which is enforced at put/load time):
        - approved_at and approved_by must be non-empty
        - expires_at, if present, must not have passed
        """
        if not manifest.get("approved_at") or not manifest.get("approved_by"):
            return "missing_approval_fields"

        expires_at = manifest.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > expiry:
                    return f"expired_at:{expires_at}"
            except ValueError as exc:
                return f"invalid_expires_at:{exc}"

        return None

    def manifest_ids(self) -> list[str]:
        return list(self._manifests.keys())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _validate_schema(self, manifest: dict) -> Optional[str]:
        errors = list(self._validator.iter_errors(manifest))
        if not errors:
            return None
        return "; ".join(e.message for e in errors[:3])
