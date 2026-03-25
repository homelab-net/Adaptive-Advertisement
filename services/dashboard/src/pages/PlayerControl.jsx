import React from 'react'
import { PlayCircle, ShieldAlert, Hand, List } from 'lucide-react'
import StubPage from '../components/StubPage'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'

function WireframePreview() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <MetricCard title="Playback Status" value="PLAYING" icon={PlayCircle} accent="green" subtext="Summer Sale Banner" />
        <MetricCard title="Safe Mode" value="OFF" icon={ShieldAlert} accent="slate" subtext="Adaptive mode active" />
        <MetricCard title="Queue Depth" value="3" unit="creatives" icon={List} accent="indigo" subtext="Fallback playlist" />
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Current Playback</h3>
        <div className="flex items-center gap-4">
          <div className="w-16 h-10 bg-slate-100 rounded flex items-center justify-center flex-shrink-0">
            <PlayCircle className="h-5 w-5 text-slate-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-700">Summer Sale Banner</p>
            <div className="mt-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full" style={{ width: '62%' }} />
            </div>
            <p className="text-xs text-slate-400 mt-0.5">9.3s / 15s</p>
          </div>
          <StatusBadge variant="active" label="PLAYING" />
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Fallback Playlist</h3>
        <div className="space-y-2">
          {['Brand Awareness CTA', 'Loyalty Programme Reminder', 'Summer Sale Banner'].map((name, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="text-xs text-slate-400 w-4">{i + 1}.</span>
              <span className="flex-1 text-slate-700">{name}</span>
              <StatusBadge variant="approved" size="xs" />
            </div>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Manual Override</h3>
        <div className="flex items-center gap-3">
          <Hand className="h-5 w-5 text-slate-400" />
          <p className="text-sm text-slate-600">Select a creative to play immediately, bypassing the decision engine</p>
          <button disabled className="ml-auto text-xs font-medium bg-indigo-100 text-indigo-400 rounded-lg px-3 py-1.5 cursor-not-allowed">
            Override
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PlayerControl() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Player Control</h1>
        <p className="text-sm text-slate-500 mt-0.5">Ad playback controller and safe mode management</p>
      </div>
      <StubPage
        phase={3}
        title="Player Control Panel"
        description="Current playback status, safe mode toggle, manual creative override, and fallback playlist management will be available once the player service is deployed in Phase 3."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
