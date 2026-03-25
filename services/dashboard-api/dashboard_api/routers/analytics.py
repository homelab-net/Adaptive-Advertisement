"""
Analytics router — privacy-safe aggregated audience summaries and impressions.

GET  /api/v1/analytics/summary              — rolling 1-hour audience aggregate
GET  /api/v1/analytics/play-events          — paginated impression log
GET  /api/v1/analytics/campaigns/{id}/summary — per-campaign impression counts
GET  /api/v1/analytics/uptime               — player uptime SLO summary

Privacy rules enforced here:
- No individual-level data is returned.
- No tracking IDs, session IDs, or persistent identifiers.
- Only aggregate counts and coarse demographic bins.
- Consistent with the locked invariants: no identity recognition, no
  cross-visit tracking, metadata-only posture.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import AudienceSnapshot, PlayEvent, UptimeEvent, Campaign, CampaignManifest
from ..schemas import (
    AnalyticsSummaryOut,
    PlayEventOut,
    PlayEventListOut,
    CampaignAnalyticsOut,
    UptimeSummaryOut,
    Pagination,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_SLO_TARGET_PCT = 99.5


# ---------------------------------------------------------------------------
# Audience summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary(
    db: AsyncSession = Depends(get_session),
) -> AnalyticsSummaryOut:
    """
    Rolling 1-hour aggregated audience summary from audience_snapshots.
    Privacy-safe: aggregate counts and coarse demographic bins only.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)

    q = select(AudienceSnapshot).where(AudienceSnapshot.sampled_at >= window_start)
    rows = (await db.execute(q)).scalars().all()

    if not rows:
        return AnalyticsSummaryOut(
            window_description="rolling 1 hour",
            sampled_at=now,
            total_observations=0,
            avg_count_per_window=None,
            peak_count=None,
            age_distribution=None,
            data_available=False,
        )

    counts = [r.presence_count for r in rows]
    avg_count = sum(counts) / len(counts)
    peak_count = max(counts)

    # Aggregate demographic bins — only from rows where demographics are available
    demo_rows = [r for r in rows if not r.demographics_suppressed]
    age_distribution: Optional[dict] = None
    if demo_rows:
        bins = {
            "child": sum(r.age_group_child or 0.0 for r in demo_rows) / len(demo_rows),
            "young_adult": sum(r.age_group_young_adult or 0.0 for r in demo_rows) / len(demo_rows),
            "adult": sum(r.age_group_adult or 0.0 for r in demo_rows) / len(demo_rows),
            "senior": sum(r.age_group_senior or 0.0 for r in demo_rows) / len(demo_rows),
        }
        # Only include if at least one bin is non-zero
        if any(v > 0 for v in bins.values()):
            age_distribution = bins

    return AnalyticsSummaryOut(
        window_description="rolling 1 hour",
        sampled_at=now,
        total_observations=len(rows),
        avg_count_per_window=round(avg_count, 2),
        peak_count=peak_count,
        age_distribution=age_distribution,
        data_available=True,
    )


# ---------------------------------------------------------------------------
# Play events (impression log)
# ---------------------------------------------------------------------------

@router.get("/play-events", response_model=PlayEventListOut)
async def list_play_events(
    manifest_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_session),
) -> PlayEventListOut:
    """Paginated impression log. Optionally filtered by manifest_id."""
    from ..config import settings as cfg
    page_size = min(page_size or cfg.default_page_size, cfg.max_page_size)

    q = select(PlayEvent)
    if manifest_id:
        q = q.where(PlayEvent.manifest_id == manifest_id)
    q = q.order_by(PlayEvent.activated_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    return PlayEventListOut(
        items=[PlayEventOut.model_validate(r) for r in rows],
        pagination=Pagination(
            total=total, page=page, page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


# ---------------------------------------------------------------------------
# Campaign impression analytics
# ---------------------------------------------------------------------------

@router.get("/campaigns/{campaign_id}/summary", response_model=CampaignAnalyticsOut)
async def get_campaign_analytics(
    campaign_id: str,
    db: AsyncSession = Depends(get_session),
) -> CampaignAnalyticsOut:
    """
    Per-campaign impression summary.

    Joins play_events against campaign_manifests to count impressions
    for each manifest in the campaign.
    """
    from fastapi import HTTPException
    campaign_row = (
        await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    ).scalar_one_or_none()
    if campaign_row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get manifest_ids for this campaign
    cm_rows = (
        await db.execute(
            select(CampaignManifest).where(CampaignManifest.campaign_id == campaign_id)
        )
    ).scalars().all()
    manifest_ids = [cm.manifest_id for cm in cm_rows]

    breakdown = []
    total_impressions = 0
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None

    for mid in manifest_ids:
        count_result = (
            await db.execute(
                select(func.count()).select_from(
                    select(PlayEvent).where(PlayEvent.manifest_id == mid).subquery()
                )
            )
        ).scalar_one()
        breakdown.append({"manifest_id": mid, "impressions": count_result})
        total_impressions += count_result

    if total_impressions > 0:
        first = (
            await db.execute(
                select(PlayEvent.activated_at)
                .where(PlayEvent.manifest_id.in_(manifest_ids))
                .order_by(PlayEvent.activated_at.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        last = (
            await db.execute(
                select(PlayEvent.activated_at)
                .where(PlayEvent.manifest_id.in_(manifest_ids))
                .order_by(PlayEvent.activated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        window_start = first
        window_end = last

    return CampaignAnalyticsOut(
        campaign_id=campaign_id,
        campaign_name=campaign_row.name,
        total_impressions=total_impressions,
        manifest_breakdown=breakdown,
        window_start=window_start,
        window_end=window_end,
    )


# ---------------------------------------------------------------------------
# Uptime SLO
# ---------------------------------------------------------------------------

@router.get("/uptime", response_model=UptimeSummaryOut)
async def get_uptime_summary(
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_session),
) -> UptimeSummaryOut:
    """
    Player uptime summary for SLO tracking.

    Default: rolling 24-hour window.  Query ?hours= for a custom window (max 720 = 30 days).
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    q = select(UptimeEvent).where(UptimeEvent.sampled_at >= window_start)
    rows = (await db.execute(q)).scalars().all()

    if not rows:
        return UptimeSummaryOut(
            window_description=f"rolling {hours}h",
            sampled_at=now,
            total_probes=0,
            healthy_probes=0,
            uptime_pct=None,
            slo_target_pct=_SLO_TARGET_PCT,
            slo_met=None,
        )

    healthy = sum(1 for r in rows if r.player_status == "healthy")
    uptime_pct = round(healthy / len(rows) * 100, 2)

    return UptimeSummaryOut(
        window_description=f"rolling {hours}h",
        sampled_at=now,
        total_probes=len(rows),
        healthy_probes=healthy,
        uptime_pct=uptime_pct,
        slo_target_pct=_SLO_TARGET_PCT,
        slo_met=uptime_pct >= _SLO_TARGET_PCT,
    )
