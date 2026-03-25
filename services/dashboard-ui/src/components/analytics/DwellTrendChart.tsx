import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { BarChart2 } from 'lucide-react'
import type { HourlyBucket } from '@/types/api'

interface Props {
  series: HourlyBucket[]
  isLoading: boolean
}

// PLACEHOLDER: series data is populated once the MQTT player pipeline is live
// (requires DASHBOARD_MQTT_ENABLED=true and ICD-9 player events from hardware).
// Until then, series will be empty or all-zero and the empty state is shown.

function formatHour(isoHour: string): string {
  try {
    const d = new Date(isoHour)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  } catch {
    return isoHour
  }
}

interface TooltipPayloadEntry {
  name: string
  value: number | null
  color: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayloadEntry[]
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-md border bg-background shadow-sm px-3 py-2 text-xs space-y-1">
      <p className="font-medium text-foreground">{label ? formatHour(label) : ''}</p>
      {payload.map((entry) => {
        const displayValue =
          entry.name === 'dwell_rate' && entry.value !== null
            ? `${(entry.value * 100).toFixed(1)}%`
            : entry.value !== null
            ? String(entry.value)
            : '—'
        const friendlyName = entry.name === 'dwell_rate' ? 'Dwell %' : 'Impressions'
        return (
          <p key={entry.name} style={{ color: entry.color }}>
            {friendlyName}: <span className="font-medium">{displayValue}</span>
          </p>
        )
      })}
    </div>
  )
}

export function DwellTrendChart({ series, isLoading }: Props) {
  const isEmpty =
    isLoading ||
    series.length === 0 ||
    series.every(
      (b) => b.impressions === 0 && (b.dwell_rate === null || b.dwell_rate === 0)
    )

  if (isEmpty) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-md border border-dashed bg-muted/30">
        <div className="text-center space-y-2">
          <BarChart2 className="h-8 w-8 text-zinc-300 mx-auto" />
          <p className="text-sm text-muted-foreground max-w-xs">
            Awaiting impression data — populates once player is live
          </p>
        </div>
      </div>
    )
  }

  const chartData = series.map((b) => ({
    hour: b.hour,
    impressions: b.impressions,
    dwell_rate: b.dwell_rate,
  }))

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
        <XAxis
          dataKey="hour"
          tickFormatter={formatHour}
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        {/* Left Y axis: dwell rate (0–1) */}
        <YAxis
          yAxisId="left"
          orientation="left"
          domain={[0, 1]}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        {/* Right Y axis: impressions */}
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={36}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          verticalAlign="bottom"
          height={28}
          iconSize={10}
          formatter={(value: string) =>
            value === 'dwell_rate' ? 'Dwell %' : 'Impressions'
          }
        />
        {/* Bar: impressions per hour, fill zinc-200, right Y axis */}
        <Bar
          yAxisId="right"
          dataKey="impressions"
          fill="#e4e4e7"
          radius={[2, 2, 0, 0]}
          maxBarSize={32}
        />
        {/* Line: dwell_rate (0–1), stroke emerald-500, left Y axis, dot=false */}
        <Line
          yAxisId="left"
          dataKey="dwell_rate"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
