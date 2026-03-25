import React from 'react'
import { GitBranch, Code, History, Lightbulb } from 'lucide-react'
import StubPage from '../components/StubPage'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'

const MOCK_TRACE = [
  { ts: '14:32:01', action: 'KEEP', creative: 'Summer Sale Banner', reason: 'Audience count stable (3), confidence high (0.87)', score: 0.92 },
  { ts: '14:31:31', action: 'SWITCH', creative: 'Brand Awareness CTA', reason: 'Audience count increased (0→3), high-confidence trigger', score: 0.78 },
  { ts: '14:31:01', action: 'KEEP', creative: 'Brand Awareness CTA', reason: 'Low confidence suppression active (0.23)', score: 0.61 },
  { ts: '14:30:31', action: 'KEEP', creative: 'Brand Awareness CTA', reason: 'No audience detected, fallback hold', score: 0.50 },
]

function WireframePreview() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard title="Current Reason Code" value="KEEP_STABLE" icon={Code} accent="indigo" subtext="Decision engine output" />
        <MetricCard title="Decisions / Min" value="2" icon={GitBranch} accent="blue" subtext="SWITCH events" />
        <MetricCard title="Confidence Window" value="0.87" icon={Lightbulb} accent="green" subtext="Current mean" />
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Keep/Switch History</h3>
        <div className="space-y-2">
          {MOCK_TRACE.map((entry, i) => (
            <div key={i} className="flex items-start gap-3 text-xs border-b border-slate-50 pb-2 last:border-0 last:pb-0">
              <span className="text-slate-400 font-mono w-16 flex-shrink-0">{entry.ts}</span>
              <StatusBadge
                variant={entry.action === 'KEEP' ? 'online' : 'starting'}
                label={entry.action}
                size="xs"
              />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-700 truncate">{entry.creative}</p>
                <p className="text-slate-400 truncate">{entry.reason}</p>
              </div>
              <span className="text-slate-500 font-semibold flex-shrink-0">{entry.score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-amber-500" />
          Explainability Trace
        </h3>
        <div className="font-mono text-xs bg-slate-50 rounded p-3 space-y-1 text-slate-600">
          <p><span className="text-indigo-600">input:</span> persons=3, confidence=0.87, window_ms=100</p>
          <p><span className="text-indigo-600">rule:</span> HIGH_CONFIDENCE_AUDIENCE → SWITCH_ELIGIBLE</p>
          <p><span className="text-indigo-600">score:</span> current_creative_score=0.92 &gt; switch_threshold=0.75</p>
          <p><span className="text-indigo-600">output:</span> action=KEEP, reason=KEEP_STABLE</p>
        </div>
      </div>
    </div>
  )
}

export default function DecisionTrace() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Decision Trace</h1>
        <p className="text-sm text-slate-500 mt-0.5">Creative selection reasoning and explainability</p>
      </div>
      <StubPage
        phase={4}
        title="Decision Engine Trace"
        description="Current creative reason codes, keep/switch history, and full explainability traces will be available once the decision-engine service is deployed in Phase 4."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
