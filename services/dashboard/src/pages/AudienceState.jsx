import React from 'react'
import { Users, Gauge, Clock, ShieldOff } from 'lucide-react'
import StubPage from '../components/StubPage'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'

function WireframePreview() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard title="Smoothed Count" value="3" unit="persons" icon={Users} accent="indigo" subtext="EMA smoothed" />
        <MetricCard title="Confidence State" value="HIGH" icon={Gauge} accent="green" subtext="Score: 0.87" />
        <MetricCard title="State Freshness" value="1.2" unit="s ago" icon={Clock} accent="blue" subtext="Last update" />
        <MetricCard title="Suppression" value="OFF" icon={ShieldOff} accent="slate" subtext="Above threshold" />
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Audience State History</h3>
        <div className="space-y-2">
          {['high', 'high', 'medium', 'low', 'medium'].map((state, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="text-xs text-slate-400 w-16">{`${i * 30}s ago`}</div>
              <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${state === 'high' ? 'bg-green-400' : state === 'medium' ? 'bg-amber-400' : 'bg-red-300'}`}
                  style={{ width: state === 'high' ? '85%' : state === 'medium' ? '55%' : '25%' }}
                />
              </div>
              <StatusBadge variant={state === 'high' ? 'online' : state === 'medium' ? 'warning' : 'error'} label={state.toUpperCase()} size="xs" />
            </div>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-2">Low-Confidence Suppression</h3>
        <div className="flex items-center gap-3">
          <div className="h-3 w-3 rounded-full bg-green-400" />
          <p className="text-sm text-slate-600">Active — confidence above suppression threshold (0.45)</p>
        </div>
      </div>
    </div>
  )
}

export default function AudienceState() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Audience State</h1>
        <p className="text-sm text-slate-500 mt-0.5">Smoothed audience metrics and confidence engine</p>
      </div>
      <StubPage
        phase={2}
        title="Audience State Engine"
        description="Smoothed person counts, confidence scoring, and low-confidence suppression will appear here once the audience-state service is deployed in Phase 2."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
