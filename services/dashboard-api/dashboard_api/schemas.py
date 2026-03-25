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
    data_available: bool


class PlayEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    manifest_id: str
    activated_at: datetime
    reason: Optional[str] = None
    prev_manifest_id: Optional[str] = None
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
