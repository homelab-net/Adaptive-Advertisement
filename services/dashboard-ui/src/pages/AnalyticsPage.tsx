import { useState, type ElementType } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart2,
  Users,
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCw,
  FlaskConical,
  Star,
} from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type {
  ManifestStats,
  AudienceComposition,
} from '@/types/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ManifestStatsGrid } from '@/components/analytics/ManifestStatsGrid'
import { DwellTrendChart } from '@/components/analytics/DwellTrendChart'
import { AudienceSegmentChart } from '@/components/analytics/AudienceSegmentChart'
import { AdaptiveAdvantageCard } from '@/components/analytics/AdaptiveAdvantageCard'

type WindowOption = '1h' | '4h' | '24h' | '7d'
type TabId = 'overview' | 'detail' | 'compare'

const WINDOW_OPTIONS: { value: WindowOption; label: string }[] = [
  { value: '1h', label: 'Last 1 hour' },
  { value: '4h', label: 'Last 4 hours' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
]

const TABS: { id: TabId; label: string; icon: ElementType }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart2 },
  { id: 'detail', label: 'Manifest Detail', icon: Activity },
  { id: 'compare', label: 'Compare A/B', icon: FlaskConical },
]

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------

function WindowPicker({
  value,
  onChange,
}: {
  value: WindowOption
  onChange: (v: WindowOption) => void
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as WindowOption)}>
      <SelectTrigger className="w-[160px] h-8 text-sm">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {WINDOW_OPTIONS.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function TrendIndicator({ direction }: { direction: string }) {
  if (direction === 'up')
    return <TrendingUp className="h-4 w-4 text-emerald-500 inline" />
  if (direction === 'down')
    return <TrendingDown className="h-4 w-4 text-red-500 inline" />
  if (direction === 'flat')
    return <span className="text-zinc-400 text-sm leading-none">→</span>
  return <span className="text-zinc-300 text-sm leading-none">—</span>
}

function OutcomeBadge({ dwell }: { dwell: boolean | null }) {
  if (dwell === true) return <Badge variant="enabled">Dwell</Badge>
  if (dwell === false) return <Badge variant="paused">No-Dwell</Badge>
  return <Badge>Interrupted</Badge>
}

// ---------------------------------------------------------------------------
// Tab 1: Overview
// ---------------------------------------------------------------------------

function OverviewTab({
  onSelectManifest,
}: {
  onSelectManifest: (id: string) => void
}) {
  const [window, setWindow] = useState<WindowOption>('24h')

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['analytics-manifests', window],
    queryFn: () => api.analytics.manifestList({ window }),
    refetchInterval: 60_000,
  })

  const noData = !isLoading && !!data && !data.data_available

  // Find highest dwell_completion_rate manifest id for the star
  let topManifestId: string | null = null
  if (data?.items && data.items.length > 0) {
    let bestRate = -Infinity
    for (const m of data.items) {
      if (m.dwell_completion_rate !== null && m.dwell_completion_rate > bestRate) {
        bestRate = m.dwell_completion_rate
        topManifestId = m.manifest_id
      }
    }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <WindowPicker value={window} onChange={setWindow} />
          {data?.items && (
            <span className="text-xs text-muted-foreground">
              {data.items.length} manifest{data.items.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isRefetching ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Loading */}
      {isLoading && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Loading impression data…
          </CardContent>
        </Card>
      )}

      {/* Empty state — no impression data yet */}
      {noData && (
        <Card>
          <CardContent className="py-16 flex flex-col items-center gap-3">
            <BarChart2 className="h-8 w-8 text-zinc-300" />
            <div className="text-center space-y-1 max-w-sm">
              <p className="text-sm font-medium text-foreground">No impression data yet</p>
              <p className="text-xs text-muted-foreground">
                Impressions are recorded automatically once the player is serving approved
                content and the MQTT pipeline is live.{' '}
                {/* PLACEHOLDER: requires DASHBOARD_MQTT_ENABLED=true and PLAYER_MQTT_ENABLED=true. */}
                PLACEHOLDER: requires DASHBOARD_MQTT_ENABLED=true and
                PLAYER_MQTT_ENABLED=true.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Leaderboard */}
      {!isLoading && data?.data_available && data.items.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Impression Leaderboard</CardTitle>
            <CardDescription>Click a row to open Manifest Detail</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/40">
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Manifest
                    </th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Status
                    </th>
                    <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Impressions
                    </th>
                    <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Avg Aud
                    </th>
                    <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs w-[180px]">
                      Dwell%
                    </th>
                    <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Reach
                    </th>
                    <th className="text-center px-4 py-2.5 font-medium text-muted-foreground text-xs">
                      Trend
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((m) => {
                    const dwellPct =
                      m.dwell_completion_rate !== null
                        ? m.dwell_completion_rate * 100
                        : null
                    const isTop = m.manifest_id === topManifestId
                    return (
                      <tr
                        key={m.manifest_id}
                        className="border-b last:border-0 hover:bg-muted/30 cursor-pointer transition-colors"
                        onClick={() => onSelectManifest(m.manifest_id)}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            {isTop && (
                              <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400 shrink-0" />
                            )}
                            <div>
                              <p className="font-medium truncate max-w-[180px]">
                                {m.title ?? m.manifest_id}
                              </p>
                              <p className="text-xs text-muted-foreground font-mono">
                                {m.manifest_id}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={m.status ?? 'draft'}>
                            {m.status ?? '—'}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {m.total_impressions.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {m.avg_audience_count !== null
                            ? m.avg_audience_count.toFixed(1)
                            : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 rounded-full bg-zinc-100 overflow-hidden min-w-[60px]">
                              {dwellPct !== null && (
                                <div
                                  className="h-full rounded-full bg-emerald-500"
                                  style={{ width: `${Math.min(dwellPct, 100)}%` }}
                                />
                              )}
                            </div>
                            <span className="text-xs tabular-nums w-10 text-right">
                              {dwellPct !== null ? `${dwellPct.toFixed(1)}%` : '—'}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {m.total_reach.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <TrendIndicator direction={m.trend_direction} />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Data available but list is empty */}
      {!isLoading && data?.data_available && data.items.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No manifests with impression data in this window.
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 2: Manifest Detail
// ---------------------------------------------------------------------------

function DetailTab({
  manifestList,
  initialManifestId,
}: {
  manifestList: ManifestStats[]
  initialManifestId: string | null
}) {
  const [selectedId, setSelectedId] = useState<string>(initialManifestId ?? '')
  const [window, setWindow] = useState<WindowOption>('24h')

  const { data, isLoading } = useQuery({
    queryKey: ['analytics-detail', selectedId, window],
    queryFn: () => api.analytics.manifestDetail(selectedId, { window }),
    enabled: !!selectedId,
  })

  const composition: AudienceComposition | null = data?.audience_composition ?? null

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger className="w-[240px] h-8 text-sm">
            <SelectValue placeholder="Select a manifest…" />
          </SelectTrigger>
          <SelectContent>
            {manifestList.map((m) => (
              <SelectItem key={m.manifest_id} value={m.manifest_id}>
                {m.title ?? m.manifest_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <WindowPicker value={window} onChange={setWindow} />
      </div>

      {/* Prompt when nothing selected */}
      {!selectedId && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Select a manifest above to view detailed impression metrics.
          </CardContent>
        </Card>
      )}

      {selectedId && (
        <>
          {/* KPI grid */}
          <ManifestStatsGrid
            stats={data?.stats ?? null}
            isLoading={isLoading}
          />

          {/* Dwell trend chart */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Hourly Dwell Trend</CardTitle>
              <CardDescription>
                Impression volume (bars, right axis) and dwell completion rate (line, left
                axis) per hour
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DwellTrendChart
                series={data?.hourly_series ?? []}
                isLoading={isLoading}
              />
            </CardContent>
          </Card>

          {/* Audience composition */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Audience Composition</CardTitle>
              <CardDescription>
                {/* PLACEHOLDER: requires ICD-3 CV age-bin signals from hardware. */}
                Probabilistic age distribution — no individual records. PLACEHOLDER:
                requires ICD-3 CV age-bin signals from hardware.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {composition === null ? (
                <div className="flex h-32 items-center justify-center rounded-md border border-dashed bg-muted/30">
                  <div className="text-center space-y-1.5">
                    <Users className="h-7 w-7 text-zinc-300 mx-auto" />
                    <p className="text-sm text-muted-foreground">
                      Demographics suppressed or unavailable
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {(
                    [
                      { key: 'child' as const, label: 'Child' },
                      { key: 'young_adult' as const, label: 'Young Adult' },
                      { key: 'adult' as const, label: 'Adult' },
                      { key: 'senior' as const, label: 'Senior' },
                    ]
                  ).map(({ key, label }) => {
                    const val = composition[key] as number | null
                    const pct = val !== null ? val * 100 : null
                    return (
                      <div key={key} className="flex items-center gap-3">
                        <span className="w-24 text-xs text-muted-foreground shrink-0">
                          {label}
                        </span>
                        <div className="flex-1 h-2 rounded-full bg-zinc-100 overflow-hidden">
                          {pct !== null && (
                            <div
                              className="h-full rounded-full bg-emerald-500"
                              style={{ width: `${Math.min(pct, 100)}%` }}
                            />
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground w-12 text-right tabular-nums">
                          {pct !== null ? `${pct.toFixed(1)}%` : '—'}
                        </span>
                      </div>
                    )
                  })}
                  {composition.suppressed_pct > 0 && (
                    <p className="text-xs text-muted-foreground pt-1">
                      {(composition.suppressed_pct * 100).toFixed(1)}% of impressions:
                      demographics suppressed
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent impressions */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Recent Impressions</CardTitle>
              <CardDescription>Last 20 recorded impression events</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {isLoading ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  Loading…
                </div>
              ) : !data?.recent_impressions ||
                data.recent_impressions.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {data && !data.data_available
                    ? 'No impression records yet — populates once player events are received.'
                    : 'No impression records in this window.'}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs">
                          Time
                        </th>
                        <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                          Duration
                        </th>
                        <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                          Audience
                        </th>
                        <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                          Confidence
                        </th>
                        <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs">
                          Outcome
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_impressions.slice(0, 20).map((imp) => (
                        <tr key={imp.id} className="border-b last:border-0">
                          <td className="px-4 py-2.5 text-xs text-muted-foreground">
                            {formatDate(imp.started_at)}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-xs">
                            {imp.duration_ms !== null
                              ? `${(imp.duration_ms / 1000).toFixed(1)}s`
                              : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-xs">
                            {imp.audience_count ?? '—'}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-xs">
                            {imp.audience_confidence !== null
                              ? `${(imp.audience_confidence * 100).toFixed(0)}%`
                              : '—'}
                          </td>
                          <td className="px-4 py-2.5">
                            <OutcomeBadge dwell={imp.dwell_elapsed ?? null} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab 3: Compare A/B
// ---------------------------------------------------------------------------

function CompareTab({ manifestList }: { manifestList: ManifestStats[] }) {
  const [manifestA, setManifestA] = useState<string>('')
  const [manifestB, setManifestB] = useState<string>('')
  const [window, setWindow] = useState<WindowOption>('24h')

  const bothSelected = !!manifestA && !!manifestB && manifestA !== manifestB

  const { data, isLoading } = useQuery({
    queryKey: ['analytics-compare', manifestA, manifestB, window],
    queryFn: () => api.analytics.compare(manifestA, manifestB, { window }),
    enabled: bothSelected,
  })

  const titleA =
    data?.manifest_a.title ??
    manifestList.find((m) => m.manifest_id === manifestA)?.title ??
    manifestA
  const titleB =
    data?.manifest_b.title ??
    manifestList.find((m) => m.manifest_id === manifestB)?.title ??
    manifestB

  // Metric values for head-to-head table
  const aImpressions = data?.manifest_a.total_impressions ?? 0
  const bImpressions = data?.manifest_b.total_impressions ?? 0
  const aDwell = data?.manifest_a.dwell_completion_rate ?? null
  const bDwell = data?.manifest_b.dwell_completion_rate ?? null
  const aReach = data?.manifest_a.total_reach ?? 0
  const bReach = data?.manifest_b.total_reach ?? 0
  const aAvgAud = data?.manifest_a.avg_audience_count ?? null
  const bAvgAud = data?.manifest_b.avg_audience_count ?? null
  const aAvgDur = data?.manifest_a.avg_duration_ms ?? null
  const bAvgDur = data?.manifest_b.avg_duration_ms ?? null

  // Returns emerald+bold class for the winning side, empty string otherwise
  function winClass(
    aVal: number | null,
    bVal: number | null,
    col: 'a' | 'b'
  ): string {
    if (aVal === null || bVal === null) return ''
    if (col === 'a' && aVal > bVal) return 'text-emerald-700 font-bold'
    if (col === 'b' && bVal > aVal) return 'text-emerald-700 font-bold'
    return ''
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">A:</span>
          <Select value={manifestA} onValueChange={setManifestA}>
            <SelectTrigger className="w-[200px] h-8 text-sm">
              <SelectValue placeholder="Manifest A…" />
            </SelectTrigger>
            <SelectContent>
              {manifestList
                .filter((m) => m.manifest_id !== manifestB)
                .map((m) => (
                  <SelectItem key={m.manifest_id} value={m.manifest_id}>
                    {m.title ?? m.manifest_id}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">B:</span>
          <Select value={manifestB} onValueChange={setManifestB}>
            <SelectTrigger className="w-[200px] h-8 text-sm">
              <SelectValue placeholder="Manifest B…" />
            </SelectTrigger>
            <SelectContent>
              {manifestList
                .filter((m) => m.manifest_id !== manifestA)
                .map((m) => (
                  <SelectItem key={m.manifest_id} value={m.manifest_id}>
                    {m.title ?? m.manifest_id}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
        <WindowPicker value={window} onChange={setWindow} />
      </div>

      {/* Prompt */}
      {!bothSelected && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Select two different manifests above to compare their performance.
          </CardContent>
        </Card>
      )}

      {bothSelected && isLoading && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Loading comparison…
          </CardContent>
        </Card>
      )}

      {bothSelected && !isLoading && data && (
        <>
          {/* Head-to-head table */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Head-to-Head Metrics</CardTitle>
              <CardDescription>
                Winning column highlighted in emerald
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40">
                      <th className="text-left px-4 py-2.5 font-medium text-muted-foreground text-xs w-[160px]">
                        Metric
                      </th>
                      <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                        {titleA}
                      </th>
                      <th className="text-right px-4 py-2.5 font-medium text-muted-foreground text-xs">
                        {titleB}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* Impressions */}
                    <tr className="border-b">
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        Impressions
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aImpressions, bImpressions, 'a')}`}
                      >
                        {aImpressions.toLocaleString()}
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aImpressions, bImpressions, 'b')}`}
                      >
                        {bImpressions.toLocaleString()}
                      </td>
                    </tr>
                    {/* Avg Audience */}
                    <tr className="border-b">
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        Avg Audience
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aAvgAud, bAvgAud, 'a')}`}
                      >
                        {aAvgAud !== null ? aAvgAud.toFixed(1) : '—'}
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aAvgAud, bAvgAud, 'b')}`}
                      >
                        {bAvgAud !== null ? bAvgAud.toFixed(1) : '—'}
                      </td>
                    </tr>
                    {/* Dwell Rate */}
                    <tr className="border-b">
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        Dwell Rate
                      </td>
                      <td
                        className={`px-4 py-3 text-right text-xs ${winClass(aDwell, bDwell, 'a')}`}
                      >
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-14 h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                            {aDwell !== null && (
                              <div
                                className="h-full rounded-full bg-emerald-500"
                                style={{ width: `${Math.min(aDwell * 100, 100)}%` }}
                              />
                            )}
                          </div>
                          <span className="tabular-nums">
                            {aDwell !== null
                              ? `${(aDwell * 100).toFixed(1)}%`
                              : '—'}
                          </span>
                        </div>
                      </td>
                      <td
                        className={`px-4 py-3 text-right text-xs ${winClass(aDwell, bDwell, 'b')}`}
                      >
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-14 h-1.5 rounded-full bg-zinc-100 overflow-hidden">
                            {bDwell !== null && (
                              <div
                                className="h-full rounded-full bg-emerald-500"
                                style={{ width: `${Math.min(bDwell * 100, 100)}%` }}
                              />
                            )}
                          </div>
                          <span className="tabular-nums">
                            {bDwell !== null
                              ? `${(bDwell * 100).toFixed(1)}%`
                              : '—'}
                          </span>
                        </div>
                      </td>
                    </tr>
                    {/* Total Reach */}
                    <tr className="border-b">
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        Total Reach
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aReach, bReach, 'a')}`}
                      >
                        {aReach.toLocaleString()}
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aReach, bReach, 'b')}`}
                      >
                        {bReach.toLocaleString()}
                      </td>
                    </tr>
                    {/* Avg Duration */}
                    <tr>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        Avg Duration
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aAvgDur, bAvgDur, 'a')}`}
                      >
                        {aAvgDur !== null
                          ? `${(aAvgDur / 1000).toFixed(1)}s`
                          : '—'}
                      </td>
                      <td
                        className={`px-4 py-3 text-right tabular-nums text-xs ${winClass(aAvgDur, bAvgDur, 'b')}`}
                      >
                        {bAvgDur !== null
                          ? `${(bAvgDur / 1000).toFixed(1)}s`
                          : '—'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Adaptive Advantage */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Adaptive Advantage</CardTitle>
            </CardHeader>
            <CardContent>
              <AdaptiveAdvantageCard
                comparison={data.comparison}
                manifestATitle={titleA}
                manifestBTitle={titleB}
                dataAvailable={data.data_available}
              />
            </CardContent>
          </Card>

          {/* Audience segment comparison */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Audience Demographics
              </CardTitle>
              <CardDescription>
                {/* PLACEHOLDER: audience_composition per-manifest in CompareResponse
                    requires dashboard-api Phase 4 compare endpoint extension.
                    Until then compositionA/B are null and the empty state renders. */}
                Grouped by age segment — PLACEHOLDER: requires ICD-3 age-bin signals
                from CV pipeline on hardware.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AudienceSegmentChart
                compositionA={
                  (
                    data.manifest_a as unknown as {
                      audience_composition?: AudienceComposition
                    }
                  ).audience_composition ?? null
                }
                compositionB={
                  (
                    data.manifest_b as unknown as {
                      audience_composition?: AudienceComposition
                    }
                  ).audience_composition ?? null
                }
                labelA={titleA}
                labelB={titleB}
              />
            </CardContent>
          </Card>

          {/* Privacy notice */}
          <p className="text-xs text-zinc-400 text-center pb-2">
            🔒 All metrics are aggregate only. No individual tracking. Audience counts
            are window averages, not per-person records.
          </p>
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

export function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [selectedManifestId, setSelectedManifestId] = useState<string | null>(null)

  // Shared manifest list used by Detail and Compare pickers
  const { data: listData } = useQuery({
    queryKey: ['analytics-manifests-shared'],
    queryFn: () => api.analytics.manifestList({}),
    refetchInterval: 60_000,
  })

  const manifestList: ManifestStats[] = listData?.items ?? []

  function handleSelectManifest(id: string) {
    setSelectedManifestId(id)
    setActiveTab('detail')
  }

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Privacy-safe aggregated impression metrics — no individual tracking
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-0 border-b mb-6">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={[
                'flex items-center gap-1.5 px-4 py-2.5 text-sm transition-colors -mb-px',
                isActive
                  ? 'border-b-2 border-primary text-foreground font-medium'
                  : 'text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <OverviewTab onSelectManifest={handleSelectManifest} />
      )}
      {activeTab === 'detail' && (
        <DetailTab
          manifestList={manifestList}
          initialManifestId={selectedManifestId}
        />
      )}
      {activeTab === 'compare' && (
        <CompareTab manifestList={manifestList} />
      )}
    </div>
  )
}
