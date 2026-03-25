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

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..events import (
    write_event,
    MANIFEST_CREATED, MANIFEST_APPROVED, MANIFEST_REJECTED,
    MANIFEST_ENABLED, MANIFEST_DISABLED, MANIFEST_ARCHIVED,
    MANIFEST_TAGS_UPDATED, MANIFEST_RULES_SYNCED,
)
from ..models import Manifest
from ..rule_generator import generate_rules_for_manifest, build_rules_file
from ..schemas import (
    ManifestIn, ManifestOut, ManifestSummary, ManifestListOut,
    ManifestTagsUpdate, RulePreviewOut, SyncRulesOut,
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
        audience_tags=body.audience_tags or [],
        status="draft",
    )
    session.add(m)
    await write_event(
        session,
        event_type=MANIFEST_CREATED,
        entity_type="manifest",
        entity_id=body.manifest_id,
        payload={
            "title": body.title,
            "schema_version": body.schema_version,
            "audience_tags": body.audience_tags,
        },
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


@router.patch("/{manifest_id}/tags", response_model=ManifestOut)
async def update_manifest_tags(
    manifest_id: str,
    body: ManifestTagsUpdate,
    session: AsyncSession = Depends(get_session),
) -> ManifestOut:
    """
    Update the audience tags on a manifest.

    Allowed in any non-archived status — tags are routing metadata, not content.
    Changing tags on an enabled manifest takes effect in the decision engine only
    after the operator triggers POST /api/v1/manifests/sync-rules.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    if m.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update tags on archived manifest '{manifest_id}'.",
        )

    old_tags = list(m.audience_tags or [])
    m.audience_tags = body.audience_tags
    m.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=MANIFEST_TAGS_UPDATED,
        entity_type="manifest",
        entity_id=manifest_id,
        payload={"old_tags": old_tags, "new_tags": body.audience_tags},
    )
    await session.commit()
    await session.refresh(m)
    return ManifestOut.model_validate(m)


@router.get("/{manifest_id}/rule-preview", response_model=RulePreviewOut)
async def get_rule_preview(
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> RulePreviewOut:
    """
    Return the decision rules that would be generated from this manifest's
    current audience_tags.  Read-only — does not write anything.

    Use this to review what will happen before calling sync-rules.
    """
    m = await _get_manifest_or_404(manifest_id, session)
    rules = generate_rules_for_manifest(m)
    return RulePreviewOut(
        manifest_id=manifest_id,
        audience_tags=list(m.audience_tags or []),
        generated_rules=rules,
    )


@router.post("/sync-rules", response_model=SyncRulesOut)
async def sync_rules(
    session: AsyncSession = Depends(get_session),
) -> SyncRulesOut:
    """
    Rebuild the generated rules file from all enabled manifests' audience_tags
    and trigger a hot-swap reload in the decision-optimizer.

    This is an explicit operator action — tag changes on enabled manifests do
    not automatically propagate to the rule engine.  The operator reviews tags
    (optionally via rule-preview) and calls this endpoint to apply them.

    The rules file is written to DASHBOARD_RULES_OUTPUT_PATH, which must be the
    same path the decision-optimizer is configured to read (shared volume).
    """
    result = await session.execute(
        select(Manifest)
        .where(Manifest.status == "enabled")
        .order_by(Manifest.enabled_at.desc())
    )
    enabled = list(result.scalars().all())

    rules_dict = build_rules_file(enabled)
    generated_count = len(rules_dict["rules"])

    # Check whether a safety fallback was injected (empty-conditions rule)
    has_fallback = any(
        len(r.get("conditions", {"x": 1})) == 0
        for r in rules_dict["rules"]
    )

    # Write rules file to disk
    rules_path = Path(settings.rules_output_path)
    optimizer_reloaded = False
    optimizer_detail: Optional[str] = None
    try:
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(
            json.dumps(rules_dict, indent=2),
            encoding="utf-8",
        )
        log.info(
            "rules file written path=%s rules=%d manifests=%d",
            rules_path, generated_count, len(enabled),
        )
    except OSError as exc:
        log.error("failed to write rules file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write rules file: {exc}",
        )

    # Trigger hot-swap reload in decision-optimizer
    reload_url = f"{settings.decision_optimizer_admin_url}/api/v1/rules/reload"
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.post(reload_url)
            resp.raise_for_status()
            optimizer_reloaded = True
            optimizer_detail = resp.text
            log.info("decision-optimizer rules reload triggered: %s", resp.status_code)
    except httpx.HTTPError as exc:
        optimizer_detail = str(exc)
        log.warning(
            "decision-optimizer reload request failed (rules file written): %s", exc
        )

    await write_event(
        session,
        event_type=MANIFEST_RULES_SYNCED,
        entity_type="manifest",
        entity_id="*",
        payload={
            "enabled_manifest_count": len(enabled),
            "generated_rule_count": generated_count,
            "has_fallback": has_fallback,
            "optimizer_reloaded": optimizer_reloaded,
        },
    )
    await session.commit()

    return SyncRulesOut(
        status="ok",
        enabled_manifests=len(enabled),
        generated_rules=generated_count,
        has_fallback=has_fallback,
        optimizer_reloaded=optimizer_reloaded,
        optimizer_detail=optimizer_detail,
    )


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
