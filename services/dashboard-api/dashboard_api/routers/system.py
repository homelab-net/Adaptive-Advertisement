"""
System router — appliance health aggregation and safe-mode control.

GET  /api/v1/status     — probe all services and return aggregated status
GET  /api/v1/safe-mode  — current safe-mode state
POST /api/v1/safe-mode  — engage safe mode
DELETE /api/v1/safe-mode — clear safe mode
GET  /api/v1/events     — paginated audit log
POST /api/v1/policy/reload — hot-swap policy rules in decision-optimizer

Safe-mode intent is stored in the safe_mode_state singleton row.
The supervisor (ICD-8) is responsible for reading this and relaying the
safe_mode command to the player via ICD-4.  dashboard-api only stores intent.

Critical services (affect `overall` = "critical" when unhealthy):
  player — playback is a hard dependency
  dashboard-api itself (implicitly healthy if this response is returned)

Non-critical services (affect `overall` = "degraded" when unhealthy):
  audience-state, decision-optimizer, creative
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..events import write_event, SAFE_MODE_ENGAGED, SAFE_MODE_CLEARED
from ..models import SafeModeState, AuditEvent, AudienceSnapshot, PlayEvent
from ..schemas import (
    SystemStatusOut, ServiceProbe, SafeModeInfo,
    SafeModeRequest, AuditEventOut, AuditEventListOut, Pagination,
    CvLiveOut, DemographicsLiveOut, PlayerLiveOut, LiveStatusOut,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

_CRITICAL_SERVICES = {"player"}


async def _probe_service(
    name: str,
    url: str,
    timeout: float,
    session: aiohttp.ClientSession,
) -> ServiceProbe:
    """HTTP GET url with timeout; returns a ServiceProbe."""
    t0 = asyncio.get_event_loop().time()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            latency_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
            if resp.status == 200:
                return ServiceProbe(
                    status="healthy",
                    probed_at=datetime.now(timezone.utc),
                    latency_ms=latency_ms,
                )
            return ServiceProbe(
                status="unhealthy",
                probed_at=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                detail=f"HTTP {resp.status}",
            )
    except asyncio.TimeoutError:
        return ServiceProbe(
            status="unreachable",
            probed_at=datetime.now(timezone.utc),
            detail="timeout",
        )
    except aiohttp.ClientError as exc:
        return ServiceProbe(
            status="unreachable",
            probed_at=datetime.now(timezone.utc),
            detail=str(exc)[:128],
        )


async def _get_or_create_safe_mode(session: AsyncSession) -> SafeModeState:
    result = await session.execute(select(SafeModeState).where(SafeModeState.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SafeModeState(id=1, is_active=False)
        session.add(row)
        await session.flush()
    return row


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/v1/status", response_model=SystemStatusOut)
async def get_system_status(
    db: AsyncSession = Depends(get_session),
) -> SystemStatusOut:
    """
    Probe all managed services and return an aggregated health snapshot.

    Probes are made concurrently; total latency = max(individual latencies).
    Playback correctness is independent of this endpoint (SYS-001).
    """
    probe_targets = {
        "player": settings.player_healthz_url,
        "audience-state": settings.audience_state_healthz_url,
        "decision-optimizer": settings.decision_optimizer_healthz_url,
        "creative": settings.creative_healthz_url,
    }

    safe_row = await _get_or_create_safe_mode(db)

    async with aiohttp.ClientSession() as http:
        results = await asyncio.gather(
            *[
                _probe_service(name, url, settings.health_probe_timeout_s, http)
                for name, url in probe_targets.items()
            ]
        )

    probes: dict[str, ServiceProbe] = dict(zip(probe_targets.keys(), results))

    # Compute overall status
    critical_unhealthy = any(
        probes[svc].status != "healthy"
        for svc in _CRITICAL_SERVICES
        if svc in probes
    )
    any_unhealthy = any(p.status != "healthy" for p in probes.values())

    if critical_unhealthy:
        overall = "critical"
    elif any_unhealthy:
        overall = "degraded"
    else:
        overall = "healthy"

    return SystemStatusOut(
        sampled_at=datetime.now(timezone.utc),
        overall=overall,
        safe_mode=SafeModeInfo(
            active=safe_row.is_active,
            reason=safe_row.reason,
            activated_at=safe_row.activated_at,
        ),
        services=probes,
    )


@router.get("/api/v1/safe-mode", response_model=SafeModeInfo)
async def get_safe_mode(
    db: AsyncSession = Depends(get_session),
) -> SafeModeInfo:
    row = await _get_or_create_safe_mode(db)
    await db.commit()
    return SafeModeInfo(
        active=row.is_active,
        reason=row.reason,
        activated_at=row.activated_at,
    )


@router.post("/api/v1/safe-mode", response_model=SafeModeInfo, status_code=status.HTTP_200_OK)
async def engage_safe_mode(
    body: SafeModeRequest,
    db: AsyncSession = Depends(get_session),
) -> SafeModeInfo:
    """
    Engage appliance safe mode.

    Stores intent in DB. The supervisor service (ICD-8) is responsible for
    polling this state and sending the safe_mode command to the player (ICD-4).
    """
    row = await _get_or_create_safe_mode(db)
    if row.is_active:
        return SafeModeInfo(active=True, reason=row.reason, activated_at=row.activated_at)

    now = datetime.now(timezone.utc)
    row.is_active = True
    row.reason = body.reason
    row.activated_at = now
    row.activated_by = body.activated_by
    row.updated_at = now

    await write_event(
        db,
        event_type=SAFE_MODE_ENGAGED,
        entity_type="system",
        entity_id="system",
        actor=body.activated_by,
        payload={"reason": body.reason},
    )
    await db.commit()
    log.warning("safe mode ENGAGED reason=%r actor=%s", body.reason, body.activated_by)
    return SafeModeInfo(active=True, reason=body.reason, activated_at=now)


@router.delete("/api/v1/safe-mode", response_model=SafeModeInfo, status_code=status.HTTP_200_OK)
async def clear_safe_mode(
    cleared_by: str = Query(default="operator"),
    db: AsyncSession = Depends(get_session),
) -> SafeModeInfo:
    """Clear safe mode."""
    row = await _get_or_create_safe_mode(db)
    if not row.is_active:
        return SafeModeInfo(active=False)

    row.is_active = False
    row.reason = None
    row.activated_at = None
    row.activated_by = None
    row.updated_at = datetime.now(timezone.utc)

    await write_event(
        db,
        event_type=SAFE_MODE_CLEARED,
        entity_type="system",
        entity_id="system",
        actor=cleared_by,
        payload={},
    )
    await db.commit()
    log.info("safe mode CLEARED actor=%s", cleared_by)
    return SafeModeInfo(active=False)


@router.get("/api/v1/events", response_model=AuditEventListOut)
async def list_events(
    event_type: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> AuditEventListOut:
    """Paginated audit event log (append-only)."""
    from ..config import settings as cfg
    page_size = min(page_size or cfg.default_page_size, cfg.max_page_size)

    q = select(AuditEvent)
    if event_type:
        q = q.where(AuditEvent.event_type == event_type)
    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditEvent.entity_id == entity_id)
    q = q.order_by(AuditEvent.created_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return AuditEventListOut(
        items=[AuditEventOut.model_validate(r) for r in rows],
        pagination=Pagination(
            total=total, page=page, page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


_CV_STALE_THRESHOLD_MS = 30_000  # snapshot older than 30 s is considered unavailable


@router.get("/api/v1/live", response_model=LiveStatusOut)
async def get_live_status(
    db: AsyncSession = Depends(get_session),
) -> LiveStatusOut:
    """
    Real-time CV pipeline and player state snapshot.

    CV data comes from the most recent audience_snapshot DB row (written by
    the audience-sink from ICD-3 MQTT signals).  Player state is inferred from
    safe_mode_state + the latest play_event row + a /healthz probe of the player
    service.  Returns null sub-objects when the respective data is unavailable.
    """
    now = datetime.now(timezone.utc)

    # --- CV: latest audience snapshot ---
    snap_result = await db.execute(
        select(AudienceSnapshot)
        .order_by(AudienceSnapshot.sampled_at.desc())
        .limit(1)
    )
    snapshot = snap_result.scalar_one_or_none()

    # --- Player: latest manifest activation + safe-mode intent ---
    play_result = await db.execute(
        select(PlayEvent).order_by(PlayEvent.activated_at.desc()).limit(1)
    )
    play_event = play_result.scalar_one_or_none()

    safe_row = await _get_or_create_safe_mode(db)

    # --- Probe player /healthz ---
    async with aiohttp.ClientSession() as http:
        player_probe = await _probe_service(
            "player", settings.player_healthz_url, settings.health_probe_timeout_s, http
        )
    player_available = player_probe.status == "healthy"

    # --- Build CV status ---
    if snapshot is not None:
        age_ms = int((now - snapshot.sampled_at).total_seconds() * 1000)
        cv_available = age_ms < _CV_STALE_THRESHOLD_MS

        age_groups: Optional[dict[str, float]] = None
        if not snapshot.demographics_suppressed:
            age_groups = {
                k: v
                for k, v in {
                    "child": snapshot.age_group_child,
                    "young_adult": snapshot.age_group_young_adult,
                    "adult": snapshot.age_group_adult,
                    "senior": snapshot.age_group_senior,
                }.items()
                if v is not None
            } or None

        cv = CvLiveOut(
            available=cv_available,
            count=snapshot.presence_count,
            confidence=snapshot.presence_confidence,
            fps=None,
            inference_ms=None,
            signal_age_ms=age_ms,
            state_stable=snapshot.state_stable,
            freeze_decision=not snapshot.state_stable,
            demographics=DemographicsLiveOut(
                age_group=age_groups,
                suppressed=snapshot.demographics_suppressed,
            ),
        )
    else:
        cv = CvLiveOut(available=False)

    # --- Build player status ---
    if safe_row.is_active:
        player_state: Optional[str] = "safe_mode"
    elif player_available and play_event is not None:
        player_state = "active"
    elif player_available:
        player_state = "fallback"
    else:
        player_state = None

    player = PlayerLiveOut(
        available=player_available,
        state=player_state,
        active_manifest_id=play_event.manifest_id if play_event else None,
        dwell_elapsed=None,
        freeze_reason=None,
        safe_mode_reason=safe_row.reason if safe_row.is_active else None,
    )

    return LiveStatusOut(cv=cv, player=player)


@router.post("/api/v1/policy/reload", status_code=status.HTTP_200_OK)
async def reload_policy() -> dict:
    """
    Relay a hot-swap request to the decision-optimizer admin endpoint.

    The decision-optimizer reloads its rules file from disk atomically.
    Returns the response from the optimizer or a 502 if unreachable.
    """
    url = settings.decision_optimizer_admin_url.rstrip("/") + "/api/v1/rules/reload"
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                url,
                timeout=aiohttp.ClientTimeout(total=5.0),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"decision-optimizer returned HTTP {resp.status}: {body}",
                    )
                log.info("policy reload relayed: %s", body)
                return body
    except aiohttp.ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"decision-optimizer unreachable: {exc}",
        ) from exc
