"""
Fallback asset management — ICD-6.

Allows the dashboard operator to list, activate, and clear fallback asset
selection in the shared fallback library volume without restarting the player.

Routes
------
GET  /api/v1/fallback-assets
    List all assets present in the fallback library directory.
    Returns each asset's name, type, and whether it is currently selected
    via the _selected marker.

POST /api/v1/fallback-assets/activate
    Body: {"name": "<filename>"}
    Pins a specific asset from the library as the active fallback by writing
    its name to the _selected marker file.  The player picks it up within
    FALLBACK_REFRESH_INTERVAL_S seconds (default 60 s) — no restart needed.

DELETE /api/v1/fallback-assets/selection
    Clears the _selected marker.  The player reverts to auto-discovery order:
    first non-reserved bundle asset → library alphabetical → built-in slate.

Notes
-----
- Only the fallback_library_dir (shared volume /data/fallback-library) is
  managed here.  Bundle assets baked into the player image are not listed
  (they are not writable by operator scripts anyway).
- All filesystem operations are confined to fallback_library_dir.
  Path traversal attempts are rejected (400).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fallback-assets", tags=["fallback-assets"])

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".mp4", ".webm",
})

_SELECTED_MARKER = "_selected"
_RESERVED: frozenset[str] = frozenset({_SELECTED_MARKER, ".gitkeep"})


def _lib_dir() -> Path:
    p = Path(settings.fallback_library_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _asset_type(name: str) -> str:
    return "video" if Path(name).suffix.lower() in {".mp4", ".webm"} else "image"


def _current_selection(lib: Path) -> Optional[str]:
    marker = lib / _SELECTED_MARKER
    if marker.exists():
        val = marker.read_text().strip()
        return val if val else None
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_fallback_assets() -> dict:
    """
    List all assets available in the fallback library.
    The player auto-selects the first item if no _selected marker is present.
    """
    lib = _lib_dir()
    selected = _current_selection(lib)
    assets = []

    if lib.exists():
        for p in sorted(lib.iterdir()):
            if p.name in _RESERVED or p.name.startswith("."):
                continue
            if p.suffix.lower() not in _ALLOWED_EXTENSIONS:
                continue
            assets.append({
                "name": p.name,
                "asset_type": _asset_type(p.name),
                "is_active": p.name == selected,
            })

    return {"assets": assets, "selected": selected}


class ActivateRequest(BaseModel):
    name: str


@router.post("/activate")
async def activate_fallback_asset(req: ActivateRequest) -> dict:
    """
    Pin a specific asset as the active fallback.
    Writes the filename to the _selected marker; player hot-swaps within
    FALLBACK_REFRESH_INTERVAL_S seconds (default 60 s).
    """
    name = req.name
    # Path traversal guard
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid asset name")
    if Path(name).suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported file extension")

    lib = _lib_dir()
    target = lib / name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="asset not found in fallback library")

    (lib / _SELECTED_MARKER).write_text(name)
    log.info("fallback asset activated: %s", name)
    return {"selected": name}


@router.delete("/selection")
async def clear_fallback_selection() -> dict:
    """
    Clear the _selected marker.  The player reverts to auto-discovery:
    first non-reserved bundle asset, then alphabetical library order,
    then the built-in dark-slate PNG.
    """
    lib = _lib_dir()
    marker = lib / _SELECTED_MARKER
    if marker.exists():
        marker.unlink()
        log.info("fallback selection cleared")
    return {"selected": None}
