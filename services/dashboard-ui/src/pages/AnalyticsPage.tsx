import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart2, RefreshCw, FlaskConical, Lock } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ManifestStatsGrid } from '@/components/analytics/ManifestStatsGrid'
import { DwellTrendChart } from '@/components/analytics/DwellTrendChart'
import { AudienceSegmentChart } from '@/components/analytics/AudienceSegmentChart'
import { AdaptiveAdvantageCard } from '@/components/analytics/AdaptiveAdvantageCard'
import type { ManifestStats } from '@/types/api'

type Tab = 'leaderboard' | 'detail' | 'compare'
type Window = '1h' | '4h' | '24h' | '7d'

const WINDOWS: { value: Window; label: string }[] = [
  { value: '1h',  label: 'Last 1 hour' },
  { value: '4h',  label: 'Last 4 hours' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d',  label: 'Last 7 days' },
]

function TrendBadge({ direction }: { direction: string }) {
  if (direction === 'up')   return <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">↑ Up</Badge>
  if (direction === 'down') return <Badge className="bg-red-100 text-red-700 border-red-200">↓ Down</Badge>
  if (direction === 'flat') return <Badge className="bg-zinc-100 text-zinc-600 border-zinc-200">→ Flat</Badge>
  return <Badge variant="secondary" className="text-xs">Insufficient data</Badge>
}

// ---------------------------------------------------------------------------
// Tab: Leaderboard
// ---------------------------------------------------------------------------

function LeaderboardTab({ window: win, onWindowChange }: { window: Window; onWindowChange: (w: Window) => void }) {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['analytics', 'manifests', win],
    queryFn: () => api.analytics.manifestList({ window: win }),
    refetchInterval: 60_000,
  })

  const items: ManifestStats[] = data?.items ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Select value={win} onValueChange={v => onWindowChange(v as Window)}>
          <SelectTrigger className="w-[160px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WINDOWS.map(w => <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
        {data && !data.data_available && (
          <span className="text-xs text-amber-600">
            {/* PLACEHOLDER: data_available=false until MQTT player pipeline is live. */}
            No impression data yet — awaiting live player events
          </span>
        )}
      </div>

      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Manifest</TableHead>
              <TableHead className="text-right">Impressions</TableHead>
              <TableHead className="text-right">Reach</TableHead>
              <TableHead className="text-right">Avg Audience</TableHead>
              <TableHead className="text-right">Dwell Rate</TableHead>
              <TableHead>Trend</TableHead>
              <TableHead className="text-right">Last Impression</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-10 text-muted-foreground text-sm">Loading…</TableCell>
              </TableRow>
            )}
            {!isLoading && items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-10 text-muted-foreground text-sm">
                  No manifest impression data for this window.
                </TableCell>
              </TableRow>
            )}
            {items.map(m => (
              <TableRow key={m.manifest_id}>
                <TableCell>
                  <div>
                    <p className="font-medium text-sm">{m.title ?? m.manifest_id}</p>
                    <p className="text-xs text-muted-foreground font-mono">{m.manifest_id}</p>
                  </div>
                </TableCell>
                <TableCell className="text-right text-sm">{m.data_available ? m.total_impressions.toLocaleString() : '—'}</TableCell>
                <TableCell className="text-right text-sm">{m.data_available ? m.total_reach.toLocaleString() : '—'}</TableCell>
                <TableCell className="text-right text-sm">{m.avg_audience_count !== null ? m.avg_audience_count.toFixed(1) : '—'}</TableCell>
                <TableCell className="text-right text-sm">
                  {m.dwell_completion_rate !== null
                    ? `${(m.dwell_completion_rate * 100).toFixed(1)}%`
                    : '—'}
                </TableCell>
                <TableCell><TrendBadge direction={m.trend_direction} /></TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">{formatDate(m.last_impression_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Manifest Detail
// ---------------------------------------------------------------------------

function DetailTab({ window: win, onWindowChange }: { window: Window; onWindowChange: (w: Window) => void }) {
  const [selectedId, setSelectedId] = useState<string>('')

  // Manifest list for the selector
  const { data: listData } = useQuery({
    queryKey: ['analytics', 'manifests', win],
    queryFn: () => api.analytics.manifestList({ window: win }),
  })

  const { data: detail, isLoading } = useQuery({
    queryKey: ['analytics', 'manifest-detail', selectedId, win],
    queryFn: () => api.analytics.manifestDetail(selectedId, { window: win }),
    enabled: !!selectedId,
  })

  const items = listData?.items ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={selectedId} onValueChange={setSelectedId}>
          <SelectTrigger className="w-[280px] h-8 text-sm">
            <SelectValue placeholder="Select a manifest…" />
          </SelectTrigger>
          <SelectContent>
            {items.map(m => (
              <SelectItem key={m.manifest_id} value={m.manifest_id}>
                {m.title ?? m.manifest_id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={win} onValueChange={v => onWindowChange(v as Window)}>
          <SelectTrigger className="w-[160px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WINDOWS.map(w => <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {!selectedId && (
        <div className="flex h-56 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
          Select a manifest to view detailed impression metrics
        </div>
      )}

      {selectedId && (
        <div className="space-y-4">
          {/* KPI row */}
          <ManifestStatsGrid stats={detail?.stats ?? null} isLoading={isLoading} />

          {/* Dwell trend chart */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Dwell Completion Trend</CardTitle>
              <CardDescription className="text-xs">
                Emerald line = dwell rate (left axis); bars = impression count (right axis)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DwellTrendChart series={detail?.hourly_series ?? []} isLoading={isLoading} />
            </CardContent>
          </Card>

          {/* Audience breakdown */}
          {detail?.audience_composition && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Audience Composition</CardTitle>
                <CardDescription className="text-xs">
                  Average age-bin fractions across impressions — probabilistic only, no individual records
                  {detail.audience_composition.suppressed_pct > 0 && (
                    <> · {(detail.audience_composition.suppressed_pct * 100).toFixed(0)}% suppressed</>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* Single-manifest view: pass null for compositionB so only A bars render */}
                <AudienceSegmentChart
                  compositionA={detail.audience_composition}
                  compositionB={null}
                  labelA={detail.title ?? selectedId}
                  labelB=""
                />
              </CardContent>
            </Card>
          )}

          {/* Recent impressions log */}
          {detail?.recent_impressions && detail.recent_impressions.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Recent Impressions</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Started</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead className="text-right">Audience</TableHead>
                      <TableHead>Dwell Elapsed</TableHead>
                      <TableHead>Ended Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.recent_impressions.map(imp => (
                      <TableRow key={imp.id}>
                        <TableCell className="text-xs text-muted-foreground">{formatDate(imp.started_at)}</TableCell>
                        <TableCell className="text-xs">{imp.duration_ms !== null ? `${(imp.duration_ms / 1000).toFixed(1)}s` : '—'}</TableCell>
                        <TableCell className="text-right text-xs">{imp.audience_count ?? '—'}</TableCell>
                        <TableCell>
                          {imp.dwell_elapsed === null ? '—' : imp.dwell_elapsed
                            ? <span className="text-xs text-emerald-600 font-medium">Yes</span>
                            : <span className="text-xs text-muted-foreground">No</span>}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{imp.ended_reason ?? '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* PLACEHOLDER: empty state when no data yet */}
          {!isLoading && detail && !detail.data_available && (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              {/* PLACEHOLDER: data_available=false until ICD-9 player events + MQTT are active on hardware. */}
              No impression data recorded for this manifest yet.
              Data populates automatically once the player publishes ICD-9 events.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Compare A/B
// ---------------------------------------------------------------------------

function CompareTab({ window: win, onWindowChange }: { window: Window; onWindowChange: (w: Window) => void }) {
  const [idA, setIdA] = useState<string>('')
  const [idB, setIdB] = useState<string>('')

  const { data: listData } = useQuery({
    queryKey: ['analytics', 'manifests', win],
    queryFn: () => api.analytics.manifestList({ window: win }),
  })

  const { data: compareData, isLoading } = useQuery({
    queryKey: ['analytics', 'compare', idA, idB, win],
    queryFn: () => api.analytics.compare(idA, idB, { window: win }),
    enabled: !!idA && !!idB && idA !== idB,
  })

  const items = listData?.items ?? []

  const ready = !!idA && !!idB && idA !== idB

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground w-5">A</span>
          <Select value={idA} onValueChange={setIdA}>
            <SelectTrigger className="w-[240px] h-8 text-sm">
              <SelectValue placeholder="Manifest A…" />
            </SelectTrigger>
            <SelectContent>
              {items.filter(m => m.manifest_id !== idB).map(m => (
                <SelectItem key={m.manifest_id} value={m.manifest_id}>
                  {m.title ?? m.manifest_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground w-5">B</span>
          <Select value={idB} onValueChange={setIdB}>
            <SelectTrigger className="w-[240px] h-8 text-sm">
              <SelectValue placeholder="Manifest B…" />
            </SelectTrigger>
            <SelectContent>
              {items.filter(m => m.manifest_id !== idA).map(m => (
                <SelectItem key={m.manifest_id} value={m.manifest_id}>
                  {m.title ?? m.manifest_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Select value={win} onValueChange={v => onWindowChange(v as Window)}>
          <SelectTrigger className="w-[160px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {WINDOWS.map(w => <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {!ready && (
        <div className="flex h-56 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
          Select two different manifests to compare their performance
        </div>
      )}

      {ready && (
        <div className="space-y-4">
          {/* Adaptive Advantage callout */}
          <AdaptiveAdvantageCard
            comparison={compareData?.comparison ?? null}
            manifestATitle={compareData?.manifest_a?.title ?? idA}
            manifestBTitle={compareData?.manifest_b?.title ?? idB}
            dataAvailable={compareData?.data_available ?? false}
          />

          {/* Side-by-side KPI summary */}
          {compareData && (
            <div className="grid grid-cols-2 gap-4">
              {([
                { label: 'A', stats: compareData.manifest_a },
                { label: 'B', stats: compareData.manifest_b },
              ] as { label: string; stats: ManifestStats }[]).map(({ label, stats }) => (
                <Card key={label}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">
                      {label}: {stats.title ?? stats.manifest_id}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <dl className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">Impressions</dt>
                        <dd className="font-medium">{stats.data_available ? stats.total_impressions.toLocaleString() : '—'}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">Reach</dt>
                        <dd className="font-medium">{stats.data_available ? stats.total_reach.toLocaleString() : '—'}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">Dwell Rate</dt>
                        <dd className="font-medium">
                          {stats.dwell_completion_rate !== null ? `${(stats.dwell_completion_rate * 100).toFixed(1)}%` : '—'}
                        </dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">Avg Audience</dt>
                        <dd className="font-medium">{stats.avg_audience_count !== null ? stats.avg_audience_count.toFixed(1) : '—'}</dd>
                      </div>
                      <div className="flex justify-between">
                        <dt className="text-muted-foreground">Trend</dt>
                        <dd><TrendBadge direction={stats.trend_direction} /></dd>
                      </div>
                    </dl>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Audience composition side-by-side */}
          {compareData && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Audience Composition Comparison</CardTitle>
                <CardDescription className="text-xs">
                  Age-bin fractions — probabilistic only, no individual records
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AudienceSegmentChart
                  compositionA={compareData.manifest_a ? null : null}
                  compositionB={null}
                  labelA={compareData?.manifest_a?.title ?? idA}
                  labelB={compareData?.manifest_b?.title ?? idB}
                />
                {/* PLACEHOLDER: audience_composition per-manifest requires dashboard-api
                    to expose it on the compare endpoint. Currently only available in
                    the manifest detail endpoint. Wire up once Phase 4 analytics endpoint
                    is extended to include audience_composition in CompareResponse. */}
                <p className="text-xs text-muted-foreground mt-2 text-center">
                  Per-manifest audience composition will populate once ICD-3 signals include age bins.
                </p>
              </CardContent>
            </Card>
          )}

          {isLoading && (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">Loading comparison…</div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Locked tab: Experiments (Phase 6)
// ---------------------------------------------------------------------------

function ExperimentsLockedTab() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-20 text-center gap-3">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <Lock className="h-5 w-5 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <p className="font-medium text-sm">Experiments — Phase 6</p>
        <p className="text-xs text-muted-foreground max-w-sm">
          {/* PLACEHOLDER: Bounded Optimizer Assistance (Phase 6) unlocks automated A/B variant
              generation within operator-approved asset bounds. Requires:
              1. Phase 5 Structured Creative Assembly infrastructure
              2. Operator-configured mutation limits in campaign settings
              3. Sufficient dwell-rate baseline from Phase 4 impression data
              4. Client approval to delegate bounded creative freedom */}
          Automated A/B variant generation within approved creative bounds.
          Unlocks in Phase 6 after establishing dwell-rate baselines.
        </p>
        <Badge variant="secondary" className="text-xs mt-2">Coming in Phase 6</Badge>
      </div>
      <div className="mt-2 rounded-md bg-muted/60 px-4 py-3 text-left max-w-sm">
        <p className="text-xs font-medium mb-1">Maturity path</p>
        <ol className="text-xs text-muted-foreground space-y-0.5 list-decimal list-inside">
          <li className="text-emerald-600 font-medium">Rules-first delivery ✓</li>
          <li className="text-emerald-600 font-medium">Controlled pilot experimentation ✓</li>
          <li>Bounded optimizer assistance ← Phase 6</li>
          <li>Continuous bounded improvement</li>
        </ol>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page root
// ---------------------------------------------------------------------------

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'leaderboard', label: 'Leaderboard', icon: BarChart2 },
  { id: 'detail',      label: 'Manifest Detail', icon: BarChart2 },
  { id: 'compare',     label: 'Compare A/B', icon: BarChart2 },
  { id: 'experiments' as Tab, label: 'Experiments', icon: FlaskConical },
]

export function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>('leaderboard')
  const [win, setWin] = useState<Window>('24h')

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Per-manifest impression metrics, dwell trends, and audience-aware A/B analysis —
          privacy-safe aggregated data only
        </p>
      </div>

      {/* Tab strip */}
      <div className="flex border-b mb-5 gap-0">
        {TABS.map(t => {
          const locked = (t.id as string) === 'experiments'
          return (
            <button
              key={t.id}
              onClick={() => !locked && setTab(t.id)}
              className={[
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                tab === t.id && !locked
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
                locked ? 'cursor-default opacity-60' : 'cursor-pointer',
              ].join(' ')}
            >
              {locked && <Lock className="h-3 w-3" />}
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'leaderboard' && <LeaderboardTab window={win} onWindowChange={setWin} />}
      {tab === 'detail'      && <DetailTab      window={win} onWindowChange={setWin} />}
      {tab === 'compare'     && <CompareTab     window={win} onWindowChange={setWin} />}
      {(tab as string) === 'experiments' && <ExperimentsLockedTab />}
    </div>
  )
}
