import React, { useState, useEffect } from 'react'
import { Users, Cpu, ShieldAlert, Hand, Activity, CheckCircle, XCircle, Info } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import ServiceCard from '../components/ServiceCard'
import StatusBadge from '../components/StatusBadge'
import LiveIndicator from '../components/LiveIndicator'
import {
  SERVICES,
  CURRENT_CV_OBSERVATION,
  CURRENT_HEALTH,
  RECENT_ACTIVITY,
  formatRelativeTime,
} from '../data/mockData'

const ACTIVITY_ICONS = {
  info: Info,
  success: CheckCircle,
  warning: ShieldAlert,
  error: XCircle,
}

const ACTIVITY_COLORS = {
  info: 'text-blue-500',
  success: 'text-green-500',
  warning: 'text-amber-500',
  error: 'text-red-500',
}

export default function Overview() {
  const [safeMode, setSafeMode] = useState(false)
  const [personCount, setPersonCount] = useState(CURRENT_CV_OBSERVATION.counts.persons)
  const [confidence, setConfidence] = useState(CURRENT_CV_OBSERVATION.counts.confidence_mean)
  const [now, setNow] = useState(Date.now())

  // Simulate live person count updates
  useEffect(() => {
    const iv = setInterval(() => {
      setPersonCount(c => Math.max(0, Math.min(8, c + Math.round((Math.random() - 0.45) * 2))))
      setConfidence(parseFloat((0.65 + Math.random() * 0.3).toFixed(2)))
      setNow(Date.now())
    }, 3000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Overview</h1>
          <p className="text-sm text-slate-500 mt-0.5">Live system snapshot — Pilot Site 1</p>
        </div>
        <LiveIndicator label="LIVE" />
      </div>

      {/* Top metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Person Count"
          value={personCount}
          unit="persons"
          subtext={`Confidence: ${(confidence * 100).toFixed(0)}%`}
          icon={Users}
          accent="indigo"
        />
        <MetricCard
          title="Pipeline FPS"
          value={CURRENT_CV_OBSERVATION.quality.pipeline_fps}
          unit="fps"
          subtext="input-cv running"
          icon={Activity}
          accent="green"
        />
        <MetricCard
          title="Inference Latency"
          value={CURRENT_CV_OBSERVATION.quality.inference_ms}
          unit="ms"
          subtext="YOLOv8n model"
          icon={Cpu}
          accent="blue"
        />
        <MetricCard
          title="Active Services"
          value="2"
          unit="/ 8"
          subtext="input-cv + mqtt-broker"
          icon={CheckCircle}
          accent="green"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Service health grid */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Service Health</h2>
            <StatusBadge variant="live" label="PARTIAL LIVE" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {SERVICES.map(service => (
              <ServiceCard
                key={service.id}
                service={service}
                healthData={service.id === 'input-cv' ? CURRENT_HEALTH : null}
                compact
              />
            ))}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* Currently playing ad */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Now Playing</h2>
              <StatusBadge variant="stub" label="PHASE 3 STUB" />
            </div>
            <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-slate-400 text-2xl">▶</span>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">No active player</p>
                  <p className="text-xs text-slate-400 mt-0.5">Player service not deployed (Phase 3)</p>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2">
                <div className="bg-slate-50 rounded p-2 text-center">
                  <p className="text-xs text-slate-500">Creative</p>
                  <p className="text-xs font-semibold text-slate-400">—</p>
                </div>
                <div className="bg-slate-50 rounded p-2 text-center">
                  <p className="text-xs text-slate-500">Duration</p>
                  <p className="text-xs font-semibold text-slate-400">—</p>
                </div>
              </div>
            </div>
          </div>

          {/* Quick actions */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Quick Actions</h2>
            </div>
            <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4 space-y-3">
              {/* Safe Mode toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className={`h-4 w-4 ${safeMode ? 'text-amber-500' : 'text-slate-400'}`} />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Safe Mode</p>
                    <p className="text-xs text-slate-400">Fallback playlist only</p>
                  </div>
                </div>
                <button
                  onClick={() => setSafeMode(v => !v)}
                  className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                    safeMode ? 'bg-amber-400 border-amber-400' : 'bg-slate-200 border-slate-200'
                  }`}
                  title="Toggle safe mode"
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${
                      safeMode ? 'translate-x-4' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
              {safeMode && (
                <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 border border-amber-200">
                  Safe mode active — only fallback ads will play
                </p>
              )}

              {/* Manual Override */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Hand className="h-4 w-4 text-slate-400" />
                  <div>
                    <p className="text-sm font-medium text-slate-700">Manual Override</p>
                    <p className="text-xs text-slate-400">Requires player (Phase 3)</p>
                  </div>
                </div>
                <button
                  disabled
                  className="text-xs font-medium bg-slate-100 text-slate-400 rounded-lg px-3 py-1.5 cursor-not-allowed"
                >
                  Disabled
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">Recent Activity</h2>
          <StatusBadge variant="stub" label="PARTIAL LIVE" />
        </div>
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm divide-y divide-slate-50">
          {RECENT_ACTIVITY.map(item => {
            const Icon = ACTIVITY_ICONS[item.level] ?? Info
            const color = ACTIVITY_COLORS[item.level] ?? 'text-slate-400'
            return (
              <div key={item.id} className="flex items-start gap-3 px-4 py-3">
                <Icon className={`h-4 w-4 flex-shrink-0 mt-0.5 ${color}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-slate-700">{item.message}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{formatRelativeTime(item.ts)}</p>
                </div>
                <span className={`flex-shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${
                  item.type === 'metric' ? 'bg-indigo-50 text-indigo-600' :
                  item.type === 'health' ? 'bg-green-50 text-green-700' :
                  'bg-slate-50 text-slate-500'
                }`}>
                  {item.type}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
