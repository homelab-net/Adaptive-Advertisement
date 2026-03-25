import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Users } from 'lucide-react'
import type { AudienceComposition } from '@/types/api'

interface Props {
  compositionA: AudienceComposition | null
  compositionB: AudienceComposition | null
  labelA: string
  labelB: string
}

// PLACEHOLDER: audience composition values are populated once ICD-3 signals
// include age bin data from the CV pipeline on hardware.
// Until then both compositionA and compositionB will be null.

const SEGMENTS = ['child', 'young_adult', 'adult', 'senior'] as const
type Segment = (typeof SEGMENTS)[number]

const SEGMENT_LABELS: Record<Segment, string> = {
  child: 'Child',
  young_adult: 'Young Adult',
  adult: 'Adult',
  senior: 'Senior',
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
      <p className="font-medium text-foreground">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}:{' '}
          <span className="font-medium">
            {entry.value !== null ? `${(entry.value * 100).toFixed(1)}%` : '—'}
          </span>
        </p>
      ))}
    </div>
  )
}

export function AudienceSegmentChart({
  compositionA,
  compositionB,
  labelA,
  labelB,
}: Props) {
  if (compositionA === null && compositionB === null) {
    return (
      <div className="flex h-[220px] items-center justify-center rounded-md border border-dashed bg-muted/30">
        <div className="text-center space-y-2">
          <Users className="h-8 w-8 text-zinc-300 mx-auto" />
          <p className="text-sm text-muted-foreground max-w-xs">
            Demographics suppressed or unavailable — populates once ICD-3 signals include age bins
          </p>
        </div>
      </div>
    )
  }

  const chartData = SEGMENTS.map((seg) => ({
    segment: SEGMENT_LABELS[seg],
    [labelA]: compositionA?.[seg] ?? 0,
    [labelB]: compositionB?.[seg] ?? 0,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <XAxis
          dataKey="segment"
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={[0, 1]}
          tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend verticalAlign="bottom" height={28} iconSize={10} />
        {/* A: emerald-400 */}
        <Bar dataKey={labelA} fill="#34d399" radius={[2, 2, 0, 0]} maxBarSize={28} />
        {/* B: zinc-300 */}
        <Bar dataKey={labelB} fill="#d4d4d8" radius={[2, 2, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}
