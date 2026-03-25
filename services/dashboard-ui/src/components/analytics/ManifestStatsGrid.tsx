import { Users, Eye, TrendingUp, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ManifestStats } from '@/types/api'

interface Props {
  stats: ManifestStats | null
  isLoading: boolean
}

interface KpiCardProps {
  icon: React.ElementType
  label: string
  value: string
  sub?: React.ReactNode
}

function KpiCard({ icon: Icon, label, value, sub }: KpiCardProps) {
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
        {sub && <div className="mt-2">{sub}</div>}
      </CardContent>
    </Card>
  )
}

// PLACEHOLDER: stats data is populated once the MQTT pipeline is live
// (requires DASHBOARD_MQTT_ENABLED=true and ICD-9 player events on hardware).
// Until then, data_available=false and all values render as "—".

export function ManifestStatsGrid({ stats, isLoading }: Props) {
  const noData = isLoading || stats === null || stats.data_available === false

  const totalImpressions = noData ? '—' : stats!.total_impressions.toLocaleString()
  const avgAudience =
    noData || stats!.avg_audience_count === null
      ? '—'
      : stats!.avg_audience_count.toFixed(1)
  const totalReach = noData ? '—' : stats!.total_reach.toLocaleString()

  const dwellRate =
    noData || stats!.dwell_completion_rate === null ? null : stats!.dwell_completion_rate
  const dwellRateValue = dwellRate !== null ? `${(dwellRate * 100).toFixed(1)}%` : '—'

  const dwellProgressBar =
    dwellRate !== null ? (
      <div className="space-y-1">
        <div className="w-full h-1.5 rounded-full bg-zinc-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all"
            style={{ width: `${Math.min(dwellRate * 100, 100)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground">0 – 100%</p>
      </div>
    ) : undefined

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        icon={Users}
        label="Total Impressions"
        value={totalImpressions}
      />
      <KpiCard
        icon={Eye}
        label="Avg Audience"
        value={avgAudience}
        sub={
          avgAudience !== '—' ? (
            <p className="text-xs text-muted-foreground">persons per impression</p>
          ) : undefined
        }
      />
      <KpiCard
        icon={TrendingUp}
        label="Dwell Rate"
        value={dwellRateValue}
        sub={dwellProgressBar}
      />
      <KpiCard
        icon={Activity}
        label="Total Reach"
        value={totalReach}
      />
    </div>
  )
}
