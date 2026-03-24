import { useQuery } from '@tanstack/react-query'
import { BarChart2, Users, TrendingUp, Eye } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

function KpiCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  )
}

export function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: api.analytics.summary,
    refetchInterval: 60_000,
  })

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Privacy-safe aggregated audience summaries — no individual tracking
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard icon={Users}    label="Total Observations"  value={isLoading ? '—' : (data?.total_observations ?? 0)} sub={data?.window_description} />
        <KpiCard icon={Eye}      label="Avg Count / Window"  value={isLoading ? '—' : (data?.avg_count_per_window?.toFixed(1) ?? '—')} sub="persons per window" />
        <KpiCard icon={TrendingUp} label="Peak Count"        value={isLoading ? '—' : (data?.peak_count ?? '—')} sub="in any single window" />
        <KpiCard icon={BarChart2}  label="Data Available"   value={isLoading ? '—' : (data?.data_available ? 'Yes' : 'No')} sub="from audience-state" />
      </div>

      {/* Placeholder chart / coming soon */}
      {data && !data.data_available && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Audience Trend</CardTitle>
            <CardDescription>
              Data will populate once the input-cv and audience-state services are running on hardware.
              The API scaffold is ready — no changes needed to enable this view.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-48 items-center justify-center rounded-md border border-dashed bg-muted/40">
              <div className="text-center">
                <BarChart2 className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">Awaiting live data</p>
                <p className="text-xs text-muted-foreground mt-1">Sampled at {formatDate(data?.sampled_at)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Age distribution — when populated */}
      {data?.age_distribution && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-sm font-medium">Age Distribution (coarse bins)</CardTitle>
            <CardDescription>Probabilistic only — no individual records stored</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(data.age_distribution).map(([bin, pct]) => (
                <div key={bin} className="flex items-center gap-3">
                  <span className="w-16 text-xs text-muted-foreground">{bin}</span>
                  <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${(pct * 100).toFixed(1)}%` }} />
                  </div>
                  <span className="text-xs text-muted-foreground w-12 text-right">{(pct * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
