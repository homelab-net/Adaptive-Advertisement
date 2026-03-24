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
