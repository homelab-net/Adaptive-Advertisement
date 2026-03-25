"""
Analytics router — privacy-safe aggregated audience summaries.

GET /api/v1/analytics/summary

For MVP, this is a scaffold that returns structure.  The actual data
source will be connected once audience-state signals are persisted to
an analytics sink table (future sprint).

Privacy rules enforced here:
- No individual-level data is returned.
- No tracking IDs, session IDs, or persistent identifiers.
- Only aggregate counts and coarse demographic bins.
- Consistent with the locked invariants: no identity recognition, no
  cross-visit tracking, metadata-only posture.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from ..schemas import AnalyticsSummaryOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def get_analytics_summary() -> AnalyticsSummaryOut:
    """
    Return a rolling aggregated audience summary.

    MVP scaffold — returns a well-structured placeholder.
    Analytics persistence (audience-state signal → analytics DB table) is
    planned for the next sprint once input-cv and audience-state are running
    on hardware.
    """
    log.debug("analytics summary requested (MVP scaffold — no data yet)")
    return AnalyticsSummaryOut(
        window_description="rolling 1 hour",
        sampled_at=datetime.now(timezone.utc),
        total_observations=0,
        avg_count_per_window=None,
        peak_count=None,
        age_distribution=None,
        data_available=False,
    )
