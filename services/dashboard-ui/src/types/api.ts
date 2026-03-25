// ICD-6 TypeScript types — mirrors dashboard_api/schemas.py

export type ManifestStatus = 'draft' | 'approved' | 'rejected' | 'enabled' | 'disabled' | 'archived'
export type CampaignStatus = 'draft' | 'active' | 'paused' | 'archived'
export type ServiceHealth = 'healthy' | 'unhealthy' | 'unreachable'
export type OverallHealth = 'healthy' | 'degraded' | 'critical'

export interface Pagination {
  total: number
  page: number
  page_size: number
  pages: number
}

// --- Manifests ---

export interface ManifestSummary {
  id: string
  manifest_id: string
  title: string
  status: ManifestStatus
  schema_version: string
  approved_at: string | null
  enabled_at: string | null
  created_at: string
  updated_at: string
}

export interface ManifestDetail extends ManifestSummary {
  manifest_json: Record<string, unknown> | null
  rejection_reason: string | null
  approved_by: string | null
}

export interface ManifestListResponse {
  items: ManifestSummary[]
  pagination: Pagination
}

// --- Assets ---

export interface AssetSummary {
  id: string
  asset_id: string
  filename: string
  asset_type: string
  size_bytes: number
  status: string
  uploaded_at: string
}

export interface AssetDetail extends AssetSummary {
  sha256: string
  manifest_id: string | null
}

export interface AssetListResponse {
  items: AssetSummary[]
  pagination: Pagination
}

// --- Campaigns ---

export interface CampaignSummary {
  id: string
  name: string
  status: CampaignStatus
  start_at: string | null
  end_at: string | null
  created_at: string
  updated_at: string
}

export interface CampaignDetail extends CampaignSummary {
  description: string | null
  manifest_ids: string[]
}

export interface CampaignListResponse {
  items: CampaignSummary[]
  pagination: Pagination
}

// --- System ---

export interface ServiceProbe {
  status: ServiceHealth
  probed_at: string
  latency_ms: number | null
  detail: string | null
}

export interface SafeModeInfo {
  active: boolean
  reason: string | null
  activated_at: string | null
}

export interface SystemStatus {
  sampled_at: string
  overall: OverallHealth
  safe_mode: SafeModeInfo
  services: Record<string, ServiceProbe>
}

// --- Analytics ---

export interface AnalyticsSummary {
  window_description: string
  sampled_at: string
  total_observations: number
  avg_count_per_window: number | null
  peak_count: number | null
  age_distribution: Record<string, number> | null
  data_available: boolean
}

// --- Audit Events ---

export interface AuditEvent {
  id: string
  event_type: string
  entity_type: string
  entity_id: string
  actor: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface AuditEventListResponse {
  items: AuditEvent[]
  pagination: Pagination
}

// --- Analytics: per-manifest impression metrics ---
// All fields are null / data_available=false until ImpressionRecorder is live
// (requires DASHBOARD_MQTT_ENABLED=true + ICD-9 player events on hardware).

export interface ManifestStats {
  manifest_id: string
  title: string | null
  status: string | null
  total_impressions: number
  avg_audience_count: number | null
  avg_duration_ms: number | null
  /** Fraction 0.0–1.0 — null until impressions are recorded */
  dwell_completion_rate: number | null
  total_reach: number
  last_impression_at: string | null
  /** "up" | "down" | "flat" | "insufficient_data" */
  trend_direction: string
  data_available: boolean
}

export interface ManifestStatsListResponse {
  items: ManifestStats[]
  data_available: boolean
}

export interface HourlyBucket {
  hour: string
  impressions: number
  reach: number
  dwell_rate: number | null
}

export interface AudienceComposition {
  child: number | null
  young_adult: number | null
  adult: number | null
  senior: number | null
  suppressed_pct: number
}

export interface RecentImpression {
  id: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  audience_count: number | null
  audience_confidence: number | null
  dwell_elapsed: boolean | null
  ended_reason: string | null
}

export interface ManifestDetailResponse {
  manifest_id: string
  title: string | null
  status: string | null
  stats: ManifestStats
  hourly_series: HourlyBucket[]
  audience_composition: AudienceComposition | null
  recent_impressions: RecentImpression[]
  data_available: boolean
}

export interface ComparisonMetrics {
  dwell_rate_delta: number | null
  reach_delta: number | null
  impression_delta: number | null
  avg_audience_delta: number | null
  dominant_segment_a: string | null
  dominant_segment_b: string | null
  segments_overlap: string[]
  /** "high" | "moderate" | "low" */
  confidence: string
}

export interface CompareResponse {
  manifest_a: ManifestStats
  manifest_b: ManifestStats
  comparison: ComparisonMetrics
  data_available: boolean
}

export interface ImpressionListResponse {
  items: RecentImpression[]
  pagination: Pagination
}

// --- Live view (GET /api/v1/live) ---
// PLACEHOLDER: this endpoint is not yet built in dashboard-api.
// It will be added in a follow-up once MQTT live state caching is wired.
// Until then LiveStatus is used by OverviewPage with null values.
export interface LiveStatus {
  cv: {
    available: boolean
    count: number | null
    confidence: number | null
    fps: number | null
    inference_ms: number | null
    signal_age_ms: number | null
    state_stable: boolean | null
    freeze_decision: boolean | null
    demographics: {
      age_group: Record<string, number> | null
      suppressed: boolean
    } | null
  } | null
  player: {
    available: boolean
    state: 'fallback' | 'active' | 'frozen' | 'safe_mode' | null
    active_manifest_id: string | null
    dwell_elapsed: boolean | null
    freeze_reason: string | null
    safe_mode_reason: string | null
  } | null
}
