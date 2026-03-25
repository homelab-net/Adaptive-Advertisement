import { ShieldAlert, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { ComparisonMetrics } from '@/types/api'

interface Props {
  comparison: ComparisonMetrics | null
  manifestATitle: string | null
  manifestBTitle: string | null
  dataAvailable: boolean
}

// PLACEHOLDER: comparison data requires ICD-9 player events and MQTT enabled.
// Until impressions are recorded, dataAvailable will be false and the amber
// unavailable card is rendered.

function ConfidenceBadge({ confidence }: { confidence: string }) {
  if (confidence === 'high') {
    return (
      <Badge className="bg-emerald-100 text-emerald-800 border border-emerald-200">
        High confidence
      </Badge>
    )
  }
  if (confidence === 'moderate') {
    return (
      <Badge className="bg-zinc-100 text-zinc-600 border border-zinc-200">
        Moderate confidence
      </Badge>
    )
  }
  return (
    <Badge className="bg-amber-100 text-amber-700 border border-amber-200">
      Low confidence
    </Badge>
  )
}

export function AdaptiveAdvantageCard({
  comparison,
  manifestATitle,
  manifestBTitle,
  dataAvailable,
}: Props) {
  // Not enough data yet
  if (!dataAvailable || comparison === null) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex gap-3 items-start">
        <ShieldAlert className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
        <div className="space-y-1">
          <p className="text-sm font-medium text-amber-900">Comparison unavailable</p>
          <p className="text-xs text-amber-700">
            Comparison data available once impressions are recorded.{' '}
            {/* PLACEHOLDER: requires ICD-9 player events and MQTT enabled. */}
            PLACEHOLDER: requires ICD-9 player events and MQTT enabled.
          </p>
        </div>
      </div>
    )
  }

  const delta = comparison.dwell_rate_delta

  // No difference
  if (delta === null || delta === 0) {
    return (
      <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 flex gap-3 items-start">
        <Minus className="h-5 w-5 text-zinc-400 mt-0.5 shrink-0" />
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-zinc-700">
            No significant difference detected
          </p>
          <p className="text-xs text-zinc-500">
            Both manifests show equivalent dwell completion rates within the selected window.
          </p>
          <ConfidenceBadge confidence={comparison.confidence} />
        </div>
      </div>
    )
  }

  const aWins = delta > 0
  const winnerTitle = aWins
    ? (manifestATitle ?? 'Manifest A')
    : (manifestBTitle ?? 'Manifest B')
  const loserTitle = aWins
    ? (manifestBTitle ?? 'Manifest B')
    : (manifestATitle ?? 'Manifest A')
  const absDelta = Math.abs(delta)

  if (aWins) {
    return (
      <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 flex gap-3 items-start">
        <TrendingUp className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-emerald-900">
            <span className="font-semibold">{winnerTitle}</span> outperformed{' '}
            <span className="font-semibold">{loserTitle}</span>
          </p>
          <p className="text-2xl font-bold text-emerald-700">
            +{(absDelta * 100).toFixed(1)} pp dwell completion
          </p>
          <ConfidenceBadge confidence={comparison.confidence} />
        </div>
      </div>
    )
  }

  // B wins
  return (
    <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 flex gap-3 items-start">
      <TrendingDown className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
      <div className="space-y-1.5">
        <p className="text-sm font-medium text-emerald-900">
          <span className="font-semibold">{winnerTitle}</span> outperformed{' '}
          <span className="font-semibold">{loserTitle}</span>
        </p>
        <p className="text-2xl font-bold text-emerald-700">
          +{(absDelta * 100).toFixed(1)} pp dwell completion
        </p>
        <ConfidenceBadge confidence={comparison.confidence} />
      </div>
    </div>
  )
}
