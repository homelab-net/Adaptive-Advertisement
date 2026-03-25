"""
Analytics router — per-manifest impression analytics for A/B comparison.

Endpoints
---------
GET /api/v1/analytics/summary          — fleet-level rolling summary (legacy compat)
GET /api/v1/analytics/manifests        — per-manifest stats leaderboard
GET /api/v1/analytics/manifests/{id}   — manifest detail: trend + audience + impressions
GET /api/v1/analytics/compare          — side-by-side A/B comparison
GET /api/v1/analytics/impressions      — paginated raw impression log

PLACEHOLDER: data_available gate
----------------------------------
All endpoints check whether any impression_events rows exist.  If none
exist (ImpressionRecorder not yet live), data_available=False is returned
and numeric fields are None / empty lists.  The frontend renders honest
empty states rather than zeros.

ImpressionRecorder becomes live when:
  1. DASHBOARD_MQTT_ENABLED=true in dashboard-api environment
  2. Mosquitto broker is reachable
  3. Player is publishing ICD-9 events (PLAYER_MQTT_ENABLED=true)
  4. input-cv + audience-state are running on Jetson hardware (for ICD-3 snapshots)

Privacy rules enforced here
---------------------------
- No individual-level data returned.
- No tracking IDs, session IDs, or persistent identifiers.
- Only aggregate counts, rates, and coarse demographic bins.
- Consistent with locked invariants: no identity recognition, no
  cross-visit tracking, metadata-only posture.
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import ImpressionEvent, Manifest
from ..schemas import (
    AnalyticsSummaryOut,
    ManifestStatsOut,
    ManifestStatsListOut,
    ManifestDetailOut,
    HourlyBucket,
    AudienceCompositionOut,
    RecentImpressionOut,
    CompareOut,
    ComparisonMetrics,
    ImpressionListOut,
    Pagination,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _has_impressions(session: AsyncSession) -> bool:
    """Return True if any impression_events rows exist."""
    result = await session.execute(
        sa.select(func.count()).select_from(ImpressionEvent)
    )
    return (result.scalar() or 0) > 0


def _window_start(window: str) -> datetime:
    """Return the UTC start time for a rolling window string."""
    now = datetime.now(timezone.utc)
    mapping = {
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }
    delta = mapping.get(window, timedelta(hours=24))
    return now - delta


def _dominant_segment(composition: Optional[AudienceCompositionOut]) -> Optional[str]:
    if composition is None:
        return None
    bins = {
        "child": composition.child or 0.0,
        "young_adult": composition.young_adult or 0.0,
        "adult": composition.adult or 0.0,
        "senior": composition.senior or 0.0,
    }
    if not any(bins.values()):
        return None
    return max(bins, key=lambda k: bins[k])


async def _build_manifest_stats(
    session: AsyncSession,
    manifest_id: str,
    since: datetime,
) -> ManifestStatsOut:
    """Compute aggregate stats for a single manifest over a time window."""

    # Fetch manifest title + status from manifests table
    manifest_row = await session.execute(
        sa.select(Manifest.title, Manifest.status).where(
            Manifest.manifest_id == manifest_id
        )
    )
    manifest_meta = manifest_row.first()
    title = manifest_meta.title if manifest_meta else None
    status = manifest_meta.status if manifest_meta else None

    # Aggregate query over impression_events
    agg = await session.execute(
        sa.select(
            func.count().label("total_impressions"),
            func.avg(ImpressionEvent.audience_count).label("avg_audience_count"),
            func.avg(ImpressionEvent.duration_ms).label("avg_duration_ms"),
            func.sum(ImpressionEvent.audience_count).label("total_reach"),
            func.max(ImpressionEvent.started_at).label("last_impression_at"),
            # dwell completion rate: fraction where dwell_elapsed=true among closed impressions
            (
                func.sum(
                    case((ImpressionEvent.dwell_elapsed == True, 1), else_=0)  # noqa: E712
                ).cast(sa.Float)
                / func.nullif(
                    func.sum(
                        case((ImpressionEvent.ended_at != None, 1), else_=0)  # noqa: E711
                    ),
                    0,
                )
            ).label("dwell_completion_rate"),
        )
        .where(
            ImpressionEvent.manifest_id == manifest_id,
            ImpressionEvent.started_at >= since,
        )
    )
    row = agg.first()

    total = row.total_impressions or 0
    if total == 0:
        return ManifestStatsOut(
            manifest_id=manifest_id,
            title=title,
            status=status,
            data_available=False,
        )

    # Trend: compare dwell rate in last half-window vs. first half-window
    half = (datetime.now(timezone.utc) - since) / 2
    mid = datetime.now(timezone.utc) - half

    recent_agg = await session.execute(
        sa.select(
            func.count().label("n"),
            (
                func.sum(
                    case((ImpressionEvent.dwell_elapsed == True, 1), else_=0)  # noqa: E712
                ).cast(sa.Float)
                / func.nullif(func.count(), 0)
            ).label("dwell_rate"),
        )
        .where(
            ImpressionEvent.manifest_id == manifest_id,
            ImpressionEvent.started_at >= mid,
            ImpressionEvent.ended_at != None,  # noqa: E711
        )
    )
    prior_agg = await session.execute(
        sa.select(
            func.count().label("n"),
            (
                func.sum(
                    case((ImpressionEvent.dwell_elapsed == True, 1), else_=0)  # noqa: E712
                ).cast(sa.Float)
                / func.nullif(func.count(), 0)
            ).label("dwell_rate"),
        )
        .where(
            ImpressionEvent.manifest_id == manifest_id,
            ImpressionEvent.started_at >= since,
            ImpressionEvent.started_at < mid,
            ImpressionEvent.ended_at != None,  # noqa: E711
        )
    )
    r_row = recent_agg.first()
    p_row = prior_agg.first()

    trend_direction = "insufficient_data"
    if (r_row.n or 0) >= 3 and (p_row.n or 0) >= 3:
        r_rate = r_row.dwell_rate or 0.0
        p_rate = p_row.dwell_rate or 0.0
        delta = r_rate - p_rate
        if delta > 0.03:
            trend_direction = "up"
        elif delta < -0.03:
            trend_direction = "down"
        else:
            trend_direction = "flat"

    return ManifestStatsOut(
        manifest_id=manifest_id,
        title=title,
        status=status,
        total_impressions=total,
        avg_audience_count=round(row.avg_audience_count, 2) if row.avg_audience_count is not None else None,
        avg_duration_ms=round(row.avg_duration_ms, 0) if row.avg_duration_ms is not None else None,
        dwell_completion_rate=round(row.dwell_completion_rate, 4) if row.dwell_completion_rate is not None else None,
        total_reach=int(row.total_reach or 0),
        last_impression_at=row.last_impression_at,
        trend_direction=trend_direction,
        data_available=True,
    )


async def _build_audience_composition(
    session: AsyncSession,
    manifest_id: str,
    since: datetime,
) -> Optional[AudienceCompositionOut]:
    """Build average age-group distribution across impressions."""
    agg = await session.execute(
        sa.select(
            func.avg(ImpressionEvent.age_child).label("child"),
            func.avg(ImpressionEvent.age_young_adult).label("young_adult"),
            func.avg(ImpressionEvent.age_adult).label("adult"),
            func.avg(ImpressionEvent.age_senior).label("senior"),
            func.count().label("total"),
            func.sum(
                case((ImpressionEvent.demographics_suppressed == True, 1), else_=0)  # noqa: E712
            ).label("suppressed_count"),
        )
        .where(
            ImpressionEvent.manifest_id == manifest_id,
            ImpressionEvent.started_at >= since,
        )
    )
    row = agg.first()
    if not row or not row.total:
        return None
    suppressed_pct = (row.suppressed_count or 0) / row.total
    if suppressed_pct >= 1.0:
        return AudienceCompositionOut(suppressed_pct=suppressed_pct)
    return AudienceCompositionOut(
        child=round(row.child, 3) if row.child is not None else None,
        young_adult=round(row.young_adult, 3) if row.young_adult is not None else None,
        adult=round(row.adult, 3) if row.adult is not None else None,
        senior=round(row.senior, 3) if row.senior is not None else None,
        suppressed_pct=round(suppressed_pct, 3),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/summary  (legacy compatibility — Phase 7 scaffold)
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary(
    session: AsyncSession = Depends(get_session),
) -> AnalyticsSummaryOut:
    """
    Rolling 1-hour audience summary.

    PLACEHOLDER: audience-level fields (avg_count_per_window, peak_count,
    age_distribution) are populated once input-cv + audience-state are live
    and ImpressionRecorder is recording ICD-3 snapshots.  Until then this
    endpoint returns the impression count as total_observations and sets
    data_available according to whether any impressions exist.
    """
    since = _window_start("1h")
    has_data = await _has_impressions(session)

    if not has_data:
        return AnalyticsSummaryOut(
            window_description="rolling 1 hour",
            sampled_at=datetime.now(timezone.utc),
            total_observations=0,
            data_available=False,
        )

    count_result = await session.execute(
        sa.select(func.count())
        .select_from(ImpressionEvent)
        .where(ImpressionEvent.started_at >= since)
    )
    total = count_result.scalar() or 0

    # PLACEHOLDER: avg_count_per_window and peak_count require ICD-3
    # audience snapshots from impression_events.audience_count.
    # They will populate once hardware is live and MQTT is enabled.
    return AnalyticsSummaryOut(
        window_description="rolling 1 hour",
        sampled_at=datetime.now(timezone.utc),
        total_observations=total,
        avg_count_per_window=None,  # PLACEHOLDER: requires ICD-3 audience snapshots
        peak_count=None,             # PLACEHOLDER: requires ICD-3 audience snapshots
        age_distribution=None,       # PLACEHOLDER: requires ICD-3 age-bin snapshots
        data_available=True,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/manifests
# ---------------------------------------------------------------------------

@router.get("/manifests", response_model=ManifestStatsListOut)
async def get_manifest_stats_list(
    window: str = Query(default="24h", regex="^(1h|4h|24h|7d)$"),
    session: AsyncSession = Depends(get_session),
) -> ManifestStatsListOut:
    """
    Per-manifest performance leaderboard sorted by dwell_completion_rate desc.

    Returns stats for every manifest that has at least one impression in the
    requested window. Returns data_available=False if no impressions exist.

    PLACEHOLDER: returns data_available=False until ImpressionRecorder is live.
    """
    has_data = await _has_impressions(session)
    if not has_data:
        return ManifestStatsListOut(items=[], data_available=False)

    since = _window_start(window)

    ids_result = await session.execute(
        sa.select(ImpressionEvent.manifest_id)
        .where(ImpressionEvent.started_at >= since)
        .distinct()
    )
    manifest_ids = [row[0] for row in ids_result.fetchall()]

    items: list[ManifestStatsOut] = []
    for mid in manifest_ids:
        stats = await _build_manifest_stats(session, mid, since)
        items.append(stats)

    items.sort(
        key=lambda s: s.dwell_completion_rate if s.dwell_completion_rate is not None else -1.0,
        reverse=True,
    )

    return ManifestStatsListOut(items=items, data_available=True)


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/manifests/{manifest_id}
# ---------------------------------------------------------------------------

@router.get("/manifests/{manifest_id}", response_model=ManifestDetailOut)
async def get_manifest_detail(
    manifest_id: str,
    window: str = Query(default="24h", regex="^(1h|4h|24h|7d)$"),
    session: AsyncSession = Depends(get_session),
) -> ManifestDetailOut:
    """
    Full manifest analytics detail: aggregate stats + hourly trend +
    audience composition + recent impression log.

    PLACEHOLDER: hourly_series and audience_composition are empty until
    ImpressionRecorder is live.
    """
    since = _window_start(window)
    stats = await _build_manifest_stats(session, manifest_id, since)

    if not stats.data_available:
        return ManifestDetailOut(
            manifest_id=manifest_id,
            stats=stats,
            data_available=False,
        )

    # --- Hourly trend series ---
    now = datetime.now(timezone.utc)
    bucket_hours = {"1h": 1, "4h": 4, "24h": 24, "7d": 168}.get(window, 24)
    hourly_series: list[HourlyBucket] = []
    for h in range(bucket_hours - 1, -1, -1):
        bucket_start = now - timedelta(hours=h + 1)
        bucket_end = now - timedelta(hours=h)
        bucket_agg = await session.execute(
            sa.select(
                func.count().label("impressions"),
                func.sum(ImpressionEvent.audience_count).label("reach"),
                (
                    func.sum(
                        case((ImpressionEvent.dwell_elapsed == True, 1), else_=0)  # noqa: E712
                    ).cast(sa.Float)
                    / func.nullif(
                        func.sum(case((ImpressionEvent.ended_at != None, 1), else_=0)),  # noqa: E711
                        0,
                    )
                ).label("dwell_rate"),
            )
            .where(
                ImpressionEvent.manifest_id == manifest_id,
                ImpressionEvent.started_at >= bucket_start,
                ImpressionEvent.started_at < bucket_end,
            )
        )
        b_row = bucket_agg.first()
        hourly_series.append(HourlyBucket(
            hour=bucket_start,
            impressions=b_row.impressions or 0,
            reach=int(b_row.reach or 0),
            dwell_rate=round(b_row.dwell_rate, 3) if b_row.dwell_rate is not None else None,
        ))

    # --- Audience composition ---
    composition = await _build_audience_composition(session, manifest_id, since)

    # --- Recent impressions (last 20) ---
    recent_result = await session.execute(
        sa.select(ImpressionEvent)
        .where(
            ImpressionEvent.manifest_id == manifest_id,
            ImpressionEvent.started_at >= since,
        )
        .order_by(ImpressionEvent.started_at.desc())
        .limit(20)
    )
    recent = [RecentImpressionOut.model_validate(row) for row in recent_result.scalars()]

    return ManifestDetailOut(
        manifest_id=manifest_id,
        title=stats.title,
        status=stats.status,
        stats=stats,
        hourly_series=hourly_series,
        audience_composition=composition,
        recent_impressions=recent,
        data_available=True,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/compare
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=CompareOut)
async def compare_manifests(
    a: str = Query(..., description="Manifest ID for comparison arm A"),
    b: str = Query(..., description="Manifest ID for comparison arm B"),
    window: str = Query(default="24h", regex="^(1h|4h|24h|7d)$"),
    session: AsyncSession = Depends(get_session),
) -> CompareOut:
    """
    Side-by-side A/B comparison of two manifests.

    Returns dwell_rate_delta, reach_delta, and confidence level.
    Confidence: high ≥30 impressions each, moderate 10–29, low <10.

    dwell_rate_delta > 0 means manifest A outperforms manifest B.
    This is the primary "Adaptive Advantage" metric shown in the Compare tab.

    PLACEHOLDER: returns data_available=False until ImpressionRecorder is live.
    """
    since = _window_start(window)
    has_data = await _has_impressions(session)

    stats_a = await _build_manifest_stats(session, a, since)
    stats_b = await _build_manifest_stats(session, b, since)

    if not has_data or (not stats_a.data_available and not stats_b.data_available):
        return CompareOut(
            manifest_a=stats_a,
            manifest_b=stats_b,
            comparison=ComparisonMetrics(),
            data_available=False,
        )

    min_impressions = min(stats_a.total_impressions, stats_b.total_impressions)
    if min_impressions >= 30:
        confidence = "high"
    elif min_impressions >= 10:
        confidence = "moderate"
    else:
        confidence = "low"

    dwell_delta: Optional[float] = None
    if stats_a.dwell_completion_rate is not None and stats_b.dwell_completion_rate is not None:
        dwell_delta = round(stats_a.dwell_completion_rate - stats_b.dwell_completion_rate, 4)

    reach_delta: Optional[int] = None
    if stats_a.total_reach is not None and stats_b.total_reach is not None:
        reach_delta = stats_a.total_reach - stats_b.total_reach

    avg_aud_delta: Optional[float] = None
    if stats_a.avg_audience_count is not None and stats_b.avg_audience_count is not None:
        avg_aud_delta = round(stats_a.avg_audience_count - stats_b.avg_audience_count, 2)

    comp_a = await _build_audience_composition(session, a, since)
    comp_b = await _build_audience_composition(session, b, since)
    dom_a = _dominant_segment(comp_a)
    dom_b = _dominant_segment(comp_b)

    def _top2(c: Optional[AudienceCompositionOut]) -> list[str]:
        if c is None:
            return []
        bins = {
            "child": c.child or 0.0,
            "young_adult": c.young_adult or 0.0,
            "adult": c.adult or 0.0,
            "senior": c.senior or 0.0,
        }
        return sorted(bins, key=lambda k: bins[k], reverse=True)[:2]

    overlap = sorted(set(_top2(comp_a)) & set(_top2(comp_b)))

    return CompareOut(
        manifest_a=stats_a,
        manifest_b=stats_b,
        comparison=ComparisonMetrics(
            dwell_rate_delta=dwell_delta,
            reach_delta=reach_delta,
            impression_delta=stats_a.total_impressions - stats_b.total_impressions,
            avg_audience_delta=avg_aud_delta,
            dominant_segment_a=dom_a,
            dominant_segment_b=dom_b,
            segments_overlap=overlap,
            confidence=confidence,
        ),
        data_available=True,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/impressions
# ---------------------------------------------------------------------------

@router.get("/impressions", response_model=ImpressionListOut)
async def list_impressions(
    manifest_id: Optional[str] = Query(default=None),
    window: str = Query(default="24h", regex="^(1h|4h|24h|7d)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ImpressionListOut:
    """
    Paginated raw impression log for the Manifest Detail view.

    PLACEHOLDER: returns empty list until ImpressionRecorder is live.
    """
    since = _window_start(window)

    conditions = [ImpressionEvent.started_at >= since]
    if manifest_id:
        conditions.append(ImpressionEvent.manifest_id == manifest_id)

    total_result = await session.execute(
        sa.select(func.count())
        .select_from(ImpressionEvent)
        .where(*conditions)
    )
    total = total_result.scalar() or 0

    rows_result = await session.execute(
        sa.select(ImpressionEvent)
        .where(*conditions)
        .order_by(ImpressionEvent.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [RecentImpressionOut.model_validate(row) for row in rows_result.scalars()]

    return ImpressionListOut(
        items=items,
        pagination=Pagination(
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        ),
    )
