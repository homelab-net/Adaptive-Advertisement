/**
 * Dashboard API client.
 *
 * All requests go to /api/v1/* — the Vite dev proxy (or nginx in prod)
 * forwards these to the dashboard-api service on port 8004.
 */
import type {
  ManifestDetail, ManifestListResponse, AudienceTag, RulePreview, SyncRulesResult,
  AssetDetail, AssetListResponse,
  CampaignDetail, CampaignListResponse,
  SystemStatus, SafeModeInfo,
  AnalyticsSummary,
  AuditEventListResponse,
  ManifestStatsListResponse,
  ManifestDetailResponse,
  CompareResponse,
  ImpressionListResponse,
  LiveStatus,
} from '@/types/api'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

// --- Manifests ---

export const api = {
  manifests: {
    list: (params?: { status?: string; page?: number; page_size?: number }) => {
      const q = new URLSearchParams()
      if (params?.status)    q.set('status', params.status)
      if (params?.page)      q.set('page', String(params.page))
      if (params?.page_size) q.set('page_size', String(params.page_size))
      return request<ManifestListResponse>(`/manifests${q.size ? `?${q}` : ''}`)
    },
    get: (id: string) => request<ManifestDetail>(`/manifests/${id}`),
    create: (body: { manifest_id: string; title: string; schema_version: string; manifest_json: unknown; audience_tags?: AudienceTag[] }) =>
      request<ManifestDetail>('/manifests', { method: 'POST', body: JSON.stringify(body) }),
    updateTags: (id: string, tags: AudienceTag[]) =>
      request<ManifestDetail>(`/manifests/${id}/tags`, { method: 'PATCH', body: JSON.stringify({ audience_tags: tags }) }),
    rulePreview: (id: string) =>
      request<RulePreview>(`/manifests/${id}/rule-preview`),
    syncRules: () =>
      request<SyncRulesResult>('/manifests/sync-rules', { method: 'POST' }),
    approve: (id: string, approved_by = 'operator') =>
      request<ManifestDetail>(`/manifests/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by }) }),
    reject: (id: string, reason: string, rejected_by = 'operator') =>
      request<ManifestDetail>(`/manifests/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason, rejected_by }) }),
    enable: (id: string) =>
      request<ManifestDetail>(`/manifests/${id}/enable`, { method: 'POST' }),
    disable: (id: string) =>
      request<ManifestDetail>(`/manifests/${id}/disable`, { method: 'POST' }),
    archive: (id: string) =>
      request<ManifestDetail>(`/manifests/${id}`, { method: 'DELETE' }),
  },

  // --- Assets ---
  assets: {
    list: (params?: { page?: number }) => {
      const q = new URLSearchParams()
      if (params?.page) q.set('page', String(params.page))
      return request<AssetListResponse>(`/assets${q.size ? `?${q}` : ''}`)
    },
    get: (id: string) => request<AssetDetail>(`/assets/${id}`),
    upload: async (file: File): Promise<AssetDetail> => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${BASE}/assets`, { method: 'POST', body: form })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(detail?.detail ?? `HTTP ${res.status}`)
      }
      return res.json()
    },
    archive: (id: string) => request<AssetDetail>(`/assets/${id}`, { method: 'DELETE' }),
  },

  // --- Campaigns ---
  campaigns: {
    list: (params?: { status?: string; page?: number }) => {
      const q = new URLSearchParams()
      if (params?.status) q.set('status', params.status)
      if (params?.page)   q.set('page', String(params.page))
      return request<CampaignListResponse>(`/campaigns${q.size ? `?${q}` : ''}`)
    },
    get: (id: string) => request<CampaignDetail>(`/campaigns/${id}`),
    create: (body: { name: string; description?: string }) =>
      request<CampaignDetail>('/campaigns', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: Partial<{ name: string; status: string; description: string }>) =>
      request<CampaignDetail>(`/campaigns/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    archive: (id: string) => request<CampaignDetail>(`/campaigns/${id}`, { method: 'DELETE' }),
    addManifest: (campaignId: string, manifestId: string) =>
      request<CampaignDetail>(`/campaigns/${campaignId}/manifests/${manifestId}`, { method: 'POST' }),
    removeManifest: (campaignId: string, manifestId: string) =>
      request<CampaignDetail>(`/campaigns/${campaignId}/manifests/${manifestId}`, { method: 'DELETE' }),
  },

  // --- System ---
  system: {
    status: () => request<SystemStatus>('/status'),
    safeMode: () => request<SafeModeInfo>('/safe-mode'),
    engageSafeMode: (reason: string) =>
      request<SafeModeInfo>('/safe-mode', { method: 'POST', body: JSON.stringify({ reason, activated_by: 'operator' }) }),
    clearSafeMode: () =>
      request<SafeModeInfo>('/safe-mode?cleared_by=operator', { method: 'DELETE' }),
  },

  // --- Analytics ---
  analytics: {
    summary: () => request<AnalyticsSummary>('/analytics/summary'),

    // Per-manifest impression stats leaderboard
    manifestList: (params?: { window?: string }) => {
      const q = new URLSearchParams()
      if (params?.window) q.set('window', params.window)
      return request<ManifestStatsListResponse>(`/analytics/manifests${q.size ? `?${q}` : ''}`)
    },

    // Full manifest detail: trend + audience + impression log
    manifestDetail: (manifestId: string, params?: { window?: string }) => {
      const q = new URLSearchParams()
      if (params?.window) q.set('window', params.window)
      return request<ManifestDetailResponse>(
        `/analytics/manifests/${manifestId}${q.size ? `?${q}` : ''}`
      )
    },

    // A/B comparison of two manifests
    compare: (a: string, b: string, params?: { window?: string }) => {
      const q = new URLSearchParams({ a, b })
      if (params?.window) q.set('window', params.window)
      return request<CompareResponse>(`/analytics/compare?${q}`)
    },

    // Paginated raw impression log
    impressions: (params?: {
      manifest_id?: string
      window?: string
      page?: number
      page_size?: number
    }) => {
      const q = new URLSearchParams()
      if (params?.manifest_id) q.set('manifest_id', params.manifest_id)
      if (params?.window)      q.set('window', params.window)
      if (params?.page)        q.set('page', String(params.page))
      if (params?.page_size)   q.set('page_size', String(params.page_size))
      return request<ImpressionListResponse>(`/analytics/impressions${q.size ? `?${q}` : ''}`)
    },
  },

  // --- Live (GET /api/v1/live) ---
  // PLACEHOLDER: endpoint not yet built in dashboard-api.
  // Returns a mock-shaped null response until the endpoint exists.
  // Wire up once ImpressionRecorder MQTT caching is in place.
  live: {
    status: async (): Promise<LiveStatus> => {
      try {
        return await request<LiveStatus>('/live')
      } catch {
        // PLACEHOLDER: /api/v1/live does not exist yet.
        // Return null-safe shape so OverviewPage renders its offline state.
        return { cv: null, player: null }
      }
    },
  },

  // --- Events ---
  events: {
    list: (params?: { event_type?: string; entity_type?: string; entity_id?: string; page?: number }) => {
      const q = new URLSearchParams()
      if (params?.event_type)  q.set('event_type', params.event_type)
      if (params?.entity_type) q.set('entity_type', params.entity_type)
      if (params?.entity_id)   q.set('entity_id', params.entity_id)
      if (params?.page)        q.set('page', String(params.page))
      return request<AuditEventListResponse>(`/events${q.size ? `?${q}` : ''}`)
    },
  },
}
