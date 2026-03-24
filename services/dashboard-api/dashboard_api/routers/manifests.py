"""
Manifest router — ICD-6 approval workflow.

Approval state machine (non-bypassable):
    draft  ──approve──▶  approved  ──enable──▶  enabled
      ▲         └──reject──▶  rejected             │
      │                          │             disable
      └──────────────────────────┘                 ▼
                                               disabled
                                                   │
                                               enable ──▶ enabled

    Any non-archived state ──archive──▶ archived  (terminal)

Rules
-----
- Only approved or disabled manifests can be enabled.
- Only draft or rejected manifests can be approved.
- Archived is terminal — no further transitions.
- All transitions are logged as audit events (PRIV-006).
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..events import (
    write_event,
    MANIFEST_CREATED, MANIFEST_APPROVED, MANIFEST_REJECTED,
    MANIFEST_ENABLED, MANIFEST_DISABLED, MANIFEST_ARCHIVED,
)
from ..models import Manifest
from ..schemas import (
    ManifestIn, ManifestOut, ManifestSummary, ManifestListOut,
    ApproveRequest, RejectRequest, Pagination,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/manifests", tags=["manifests"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft":    {"approved", "rejected", "archived"},
    "approved": {"enabled", "rejected", "archived"},
    "rejected": {"approved", "archived"},
    "enabled":  {"disabled", "archived"},
    "disabled": {"enabled", "archived"},
    "archived": set(),  # terminal
}


def _can_transition(current: str, target: str) -> bool:
    return target in _VALID_TRANSITIONS.get(current, set())


def _raise_transition_error(manifest_id: str, current: str, target: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Manifest '{manifest_id}' cannot transition from "
            f"'{current}' to '{target}'."
        ),
    )


async def _get_manifest_or_404(
    manifest_id: str, session: AsyncSession
) -> Manifest:
    result = await session.execute(
        select(Manifest).where(Manifest.manifest_id == manifest_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest '{manifest_id}' not found.",
        )
    return m


def _write_manifest_to_disk(manifest: Manifest) -> None:
    """
    Write the manifest JSON to MANIFEST_OUTPUT_DIR so the creative service
    can pick it up.  Only called when status transitions to 'enabled'.
    Failures are logged but do not abort the DB transaction — the manifest
    is still recorded as enabled in the DB.
    """
    out_dir = Path(settings.manifest_output_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{manifest.manifest_id}.json"
        out_path.write_text(
            json.dumps(manifest.manifest_json, indent=2),
            encoding="utf-8",
        )
        log.info("manifest written to disk path=%s", out_path)
    except OSError as exc:
        log.error(
            "failed to write manifest to disk manifest_id=%s: %s",
            manifest.manifest_id, exc,
        )


def _remove_manifest_from_disk(manifest_id: str) -> None:
    """Remove manifest JSON from disk when disabled or archived."""
    out_path = Path(settings.manifest_output_dir) / f"{manifest_id}.json"
    try:
        out_path.unlink(missing_ok=True)
        log.info("manifest removed from disk path=%s", out_path)
    except OSError as exc:
        log.error(
            "failed to remove manifest from disk manifest_id=%s: %s",
            manifest_id, exc,
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=ManifestListOut)
async def list_manifests(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> ManifestListOut:
    """List manifests with optional status filter, paginated."""
    page_size = page_size or settings.default_page_size
    page_size = min(page_size, settings.max_page_size)

    q = select(Manifest)
    if status:
        q = q.where(Manifest.status == status)
    q = q.order_by(Manifest.created_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(q)).scalars().all()

    return ManifestListOut(
        items=[ManifestSummary.model_validate(r) for r in rows],
        pagination=Pagination(
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.post("", response_model=ManifestOut, status_code=status.HTTP_201_CREATED)
async def create_manifest(
    body: ManifestIn,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """Register a new manifest. Initial status is 'draft'."""
    # Uniqueness check
    existing = await session.execute(
        select(Manifest).where(Manifest.manifest_id == body.manifest_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"manifest_id '{body.manifest_id}' already exists.",
        )

    m = Manifest(
        manifest_id=body.manifest_id,
        title=body.title,
        schema_version=body.schema_version,
        manifest_json=body.manifest_json,
        status="draft",
    )
    session.add(m)
    await write_event(
        session,
        event_type=MANIFEST_CREATED,
        entity_type="manifest",
        entity_id=body.manifest_id,
        payload={"title": body.title, "schema_version": body.schema_version},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.get("/{manifest_id}", response_model=ManifestOut)
async def get_manifest(
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    m = await _get_manifest_or_404(manifest_id, session)
    return ManifestOut.model_validate(m)


@router.post("/{manifest_id}/approve", response_model=ManifestOut)
async def approve_manifest(
    manifest_id: str,
    body: ApproveRequest,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """
    Approve a manifest.  Allowed from: draft, rejected.
    Non-bypassable — archived manifests cannot be approved.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    if not _can_transition(m.status, "approved"):
        _raise_transition_error(manifest_id, m.status, "approved")

    prev_status = m.status
    m.status = "approved"
    m.approved_by = body.approved_by
    m.approved_at = datetime.now(timezone.utc)
    m.rejection_reason = None
    m.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=MANIFEST_APPROVED,
        entity_type="manifest",
        entity_id=manifest_id,
        actor=body.approved_by,
        payload={"previous_status": prev_status},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.post("/{manifest_id}/reject", response_model=ManifestOut)
async def reject_manifest(
    manifest_id: str,
    body: RejectRequest,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """Reject a manifest. Allowed from: draft, approved."""
    m = await _get_manifest_or_404(manifest_id, session)
    if not _can_transition(m.status, "rejected"):
        _raise_transition_error(manifest_id, m.status, "rejected")

    prev_status = m.status
    m.status = "rejected"
    m.rejection_reason = body.reason
    m.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=MANIFEST_REJECTED,
        entity_type="manifest",
        entity_id=manifest_id,
        actor=body.rejected_by,
        payload={"previous_status": prev_status, "reason": body.reason},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.post("/{manifest_id}/enable", response_model=ManifestOut)
async def enable_manifest(
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """
    Enable a manifest for playback.  Allowed from: approved, disabled.
    Writes the manifest JSON to disk so the creative service can load it.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    if not _can_transition(m.status, "enabled"):
        _raise_transition_error(manifest_id, m.status, "enabled")

    prev_status = m.status
    m.status = "enabled"
    m.enabled_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)

    _write_manifest_to_disk(m)

    await write_event(
        session,
        event_type=MANIFEST_ENABLED,
        entity_type="manifest",
        entity_id=manifest_id,
        payload={"previous_status": prev_status},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.post("/{manifest_id}/disable", response_model=ManifestOut)
async def disable_manifest(
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """
    Disable a manifest from playback.  Allowed from: enabled.
    Removes the manifest JSON from disk so the creative service stops serving it.
    Note: already-playing content continues until the player receives a new command.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    if not _can_transition(m.status, "disabled"):
        _raise_transition_error(manifest_id, m.status, "disabled")

    m.status = "disabled"
    m.updated_at = datetime.now(timezone.utc)

    _remove_manifest_from_disk(manifest_id)

    await write_event(
        session,
        event_type=MANIFEST_DISABLED,
        entity_type="manifest",
        entity_id=manifest_id,
        payload={},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.delete("/{manifest_id}", response_model=ManifestOut)
async def archive_manifest(
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """
    Archive (soft-delete) a manifest.  Allowed from any non-archived state.
    Removes manifest from disk if it was enabled.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    if not _can_transition(m.status, "archived"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Manifest '{manifest_id}' is already archived.",
        )

    prev_status = m.status
    if prev_status == "enabled":
        _remove_manifest_from_disk(manifest_id)

    m.status = "archived"
    m.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=MANIFEST_ARCHIVED,
        entity_type="manifest",
        entity_id=manifest_id,
        payload={"previous_status": prev_status},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)
