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

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .rule_generator import ALL_VALID_TAGS


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

def _validate_audience_tags(tags: list[str]) -> list[str]:
    """Validate that all tag keys are from the canonical taxonomy."""
    invalid = set(tags) - ALL_VALID_TAGS
    if invalid:
        raise ValueError(
            f"Unknown audience tag(s): {sorted(invalid)}. "
            f"Valid tags are: {sorted(ALL_VALID_TAGS)}"
        )
    if len(tags) != len(set(tags)):
        raise ValueError("Duplicate audience tags are not allowed.")
    return tags


class ManifestIn(BaseModel):
    """Body for POST /api/v1/manifests."""
    manifest_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    schema_version: str = Field(default="1.0.0")
    manifest_json: dict[str, Any] = Field(
        description="Raw ICD-5 creative manifest object."
    )
    audience_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Operator-assigned audience profile tags. Used for human-readable "
            "labelling and auto-generating decision rules. "
            "Must be keys from the canonical tag taxonomy."
        ),
    )

    @field_validator("audience_tags")
    @classmethod
    def validate_audience_tags(cls, v: list[str]) -> list[str]:
        return _validate_audience_tags(v)


class ManifestTagsUpdate(BaseModel):
    """Body for PATCH /api/v1/manifests/{manifest_id}/tags."""
    audience_tags: list[str] = Field(
        description="Replacement set of audience tags for this manifest.",
    )

    @field_validator("audience_tags")
    @classmethod
    def validate_audience_tags(cls, v: list[str]) -> list[str]:
        return _validate_audience_tags(v)


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
    audience_tags: list[str] = Field(default_factory=list)


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
    audience_tags: list[str] = Field(default_factory=list)


class ManifestListOut(BaseModel):
    items: list[ManifestSummary]
    pagination: Pagination


class RulePreviewOut(BaseModel):
    """Response for GET /api/v1/manifests/{manifest_id}/rule-preview."""
    manifest_id: str
    audience_tags: list[str]
    generated_rules: list[dict[str, Any]]


class SyncRulesOut(BaseModel):
    """Response for POST /api/v1/manifests/sync-rules."""
    status: str
    enabled_manifests: int
    generated_rules: int
    has_fallback: bool
    optimizer_reloaded: bool
    optimizer_detail: Optional[str] = None


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
    Privacy-safe aggregated analytics summary from audience_snapshots.

    Rolling-window counts only — no individual tracking, no PII.
    """
    window_description: str = "rolling 1 hour"
    sampled_at: datetime
    total_observations: int
    avg_count_per_window: Optional[float] = None
    peak_count: Optional[int] = None
    # Demographic distribution: coarse bins only, no individual records
    age_distribution: Optional[dict[str, float]] = None
    # Average gaze-toward-display probability over the window (CRM-004).
    # None when head-pose model is not active or no data in window.
    avg_attention_engaged: Optional[float] = None
    data_available: bool


class PlayEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    manifest_id: str
    activated_at: datetime
    reason: Optional[str] = None
    prev_manifest_id: Optional[str] = None
    attention_at_trigger: Optional[float] = None
    received_at: datetime


class PlayEventListOut(BaseModel):
    items: list[PlayEventOut]
    pagination: Pagination


class CampaignAnalyticsOut(BaseModel):
    """Impression summary for a single campaign."""
    campaign_id: str
    campaign_name: str
    total_impressions: int
    manifest_breakdown: list[dict[str, Any]]  # [{manifest_id, impressions}]
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    # Average attention engaged at activation time across all impressions (CRM-004).
    # None when no play events have attention data.
    avg_attention_at_trigger: Optional[float] = None


class UptimeSummaryOut(BaseModel):
    """Player uptime summary for SLO tracking."""
    window_description: str
    sampled_at: datetime
    total_probes: int
    healthy_probes: int
    uptime_pct: Optional[float] = None  # None when no data
    slo_target_pct: float = 99.5
    slo_met: Optional[bool] = None


# ---------------------------------------------------------------------------
# Live status (GET /api/v1/live)
# ---------------------------------------------------------------------------

class DemographicsLiveOut(BaseModel):
    """Coarse age-bin and attire distribution from the latest CV signal."""
    age_group: Optional[dict[str, float]] = None
    attire: Optional[dict[str, float]] = None
    suppressed: bool


class CvLiveOut(BaseModel):
    """Real-time CV pipeline state derived from the latest audience_snapshot row."""
    available: bool
    count: Optional[int] = None
    confidence: Optional[float] = None
    fps: Optional[float] = None          # Not persisted in DB; populated by future telemetry
    inference_ms: Optional[float] = None  # Not persisted in DB; populated by future telemetry
    signal_age_ms: Optional[int] = None
    state_stable: Optional[bool] = None
    freeze_decision: Optional[bool] = None
    demographics: Optional[DemographicsLiveOut] = None


class PlayerLiveOut(BaseModel):
    """Real-time player state inferred from safe_mode_state, play_events, and health probe."""
    available: bool
    state: Optional[str] = None  # "fallback" | "active" | "safe_mode"
    active_manifest_id: Optional[str] = None
    dwell_elapsed: Optional[bool] = None    # Not persisted in DB; from ICD-9 events
    freeze_reason: Optional[str] = None     # Not persisted in DB; from ICD-9 events
    safe_mode_reason: Optional[str] = None


class LiveStatusOut(BaseModel):
    cv: Optional[CvLiveOut] = None
    player: Optional[PlayerLiveOut] = None


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
