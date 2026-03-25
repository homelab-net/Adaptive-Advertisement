"""
Pydantic request/response models — ICD-6 API contract.

These types define the exact JSON shape the dashboard frontend sees.
They are intentionally decoupled from the SQLAlchemy ORM models so the
persistence layer can evolve independently.

Naming convention
-----------------
  <Entity>In   — request body (create / update)
  <Entity>Out  — response body (single item)
  <Entity>Summary — lightweight list-view item (omits heavy fields)
  <Action>Request — action-specific body (approve, reject, etc.)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class Pagination(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

class ManifestIn(BaseModel):
    """Body for POST /api/v1/manifests."""
    manifest_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    schema_version: str = Field(default="1.0.0")
    manifest_json: dict[str, Any] = Field(
        description="Raw ICD-5 creative manifest object."
    )


class ManifestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    manifest_id: str
    title: str
    status: str
    schema_version: str
    manifest_json: Optional[dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    enabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ManifestSummary(BaseModel):
    """Lightweight list-view — omits manifest_json payload."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    manifest_id: str
    title: str
    status: str
    schema_version: str
    approved_at: Optional[datetime] = None
    enabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ManifestListOut(BaseModel):
    items: list[ManifestSummary]
    pagination: Pagination


class ApproveRequest(BaseModel):
    approved_by: str = Field(default="operator", max_length=128)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1024)
    rejected_by: str = Field(default="operator", max_length=128)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    filename: str
    asset_type: str
    size_bytes: int
    sha256: str
    manifest_id: Optional[str] = None
    status: str
    uploaded_at: datetime


class AssetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    filename: str
    asset_type: str
    size_bytes: int
    status: str
    uploaded_at: datetime


class AssetListOut(BaseModel):
    items: list[AssetSummary]
    pagination: Pagination


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2048)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2048)
    status: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    manifest_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CampaignSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CampaignListOut(BaseModel):
    items: list[CampaignSummary]
    pagination: Pagination


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

class ServiceProbe(BaseModel):
    status: str  # "healthy" | "unhealthy" | "unreachable"
    probed_at: datetime
    latency_ms: Optional[int] = None
    detail: Optional[str] = None


class SafeModeInfo(BaseModel):
    active: bool
    reason: Optional[str] = None
    activated_at: Optional[datetime] = None


class SystemStatusOut(BaseModel):
    sampled_at: datetime
    overall: str  # "healthy" | "degraded" | "critical"
    safe_mode: SafeModeInfo
    services: dict[str, ServiceProbe]


class SafeModeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=512)
    activated_by: str = Field(default="operator", max_length=128)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class AnalyticsSummaryOut(BaseModel):
    """
    Privacy-safe aggregated analytics summary.

    Rolling-window counts only — no individual tracking, no PII.
    Populated from audience-state signals stored in audit_events or
    a future analytics sink table.
    """
    window_description: str = "rolling 1 hour"
    sampled_at: datetime
    total_observations: int
    avg_count_per_window: Optional[float] = None
    peak_count: Optional[int] = None
    # Demographic distribution: coarse bins only, no individual records
    age_distribution: Optional[dict[str, float]] = None
    data_available: bool


class ManifestStatsOut(BaseModel):
    """
    Per-manifest aggregate performance metrics.

    PLACEHOLDER: data_available=False until ImpressionRecorder populates
    impression_events (requires ICD-9 player events live on MQTT).
    All numeric fields are None when data_available=False.
    """
    manifest_id: str
    title: Optional[str] = None
    status: Optional[str] = None
    total_impressions: int = 0
    # Average number of persons detected at impression start
    avg_audience_count: Optional[float] = None
    # Average impression duration in milliseconds
    avg_duration_ms: Optional[float] = None
    # Fraction of impressions where dwell_elapsed=true (0.0–1.0)
    dwell_completion_rate: Optional[float] = None
    # Sum of audience_count across all impressions (person-count × impressions proxy)
    total_reach: int = 0
    last_impression_at: Optional[datetime] = None
    # "up" | "down" | "flat" | "insufficient_data"
    trend_direction: str = "insufficient_data"
    data_available: bool = False


class ManifestStatsListOut(BaseModel):
    items: list[ManifestStatsOut]
    data_available: bool


class HourlyBucket(BaseModel):
    """One hourly time-series bucket for a manifest."""
    hour: datetime
    impressions: int
    reach: int
    dwell_rate: Optional[float] = None  # None when no impressions in bucket


class AudienceCompositionOut(BaseModel):
    """
    Average age-group distribution across impressions for one manifest.
    Fractions 0.0–1.0; suppressed_pct = fraction of impressions with demographics suppressed.
    Privacy: coarse bins only; no individual records.
    """
    child: Optional[float] = None
    young_adult: Optional[float] = None
    adult: Optional[float] = None
    senior: Optional[float] = None
    suppressed_pct: float = 0.0


class RecentImpressionOut(BaseModel):
    """Lightweight impression summary for the detail view impression log."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    audience_count: Optional[int] = None
    audience_confidence: Optional[float] = None
    dwell_elapsed: Optional[bool] = None
    ended_reason: Optional[str] = None


class ManifestDetailOut(BaseModel):
    """
    Full per-manifest analytics detail including trend + audience composition.

    PLACEHOLDER: hourly_series and audience_composition are empty until
    ImpressionRecorder is live (DASHBOARD_MQTT_ENABLED=true + ICD-9 events).
    """
    manifest_id: str
    title: Optional[str] = None
    status: Optional[str] = None
    stats: ManifestStatsOut
    hourly_series: list[HourlyBucket] = Field(default_factory=list)
    audience_composition: Optional[AudienceCompositionOut] = None
    recent_impressions: list[RecentImpressionOut] = Field(default_factory=list)
    data_available: bool = False


class ComparisonMetrics(BaseModel):
    """
    Side-by-side deltas between manifest A and manifest B.

    dwell_rate_delta = A.dwell_completion_rate - B.dwell_completion_rate
    Positive value = A outperforms B on dwell.
    """
    dwell_rate_delta: Optional[float] = None
    reach_delta: Optional[int] = None
    impression_delta: Optional[int] = None
    avg_audience_delta: Optional[float] = None
    dominant_segment_a: Optional[str] = None  # highest age bin for A
    dominant_segment_b: Optional[str] = None  # highest age bin for B
    segments_overlap: list[str] = Field(default_factory=list)
    # "high" (≥30 impressions each) | "moderate" (10–29) | "low" (<10)
    confidence: str = "low"


class CompareOut(BaseModel):
    """
    A/B comparison response.

    PLACEHOLDER: all fields are None/empty until ImpressionRecorder is live.
    """
    manifest_a: ManifestStatsOut
    manifest_b: ManifestStatsOut
    comparison: ComparisonMetrics
    data_available: bool = False


class ImpressionListOut(BaseModel):
    items: list[RecentImpressionOut]
    pagination: Pagination


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor: str
    payload: Optional[dict[str, Any]] = None
    created_at: datetime


class AuditEventListOut(BaseModel):
    items: list[AuditEventOut]
    pagination: Pagination
