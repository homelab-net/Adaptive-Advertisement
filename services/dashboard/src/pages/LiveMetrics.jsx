import React, { useState, useEffect, useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  AreaChart, Area,
} from 'recharts'
import { Activity, Cpu, Camera, RefreshCw, Users, Gauge } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import StatusBadge from '../components/StatusBadge'
import LiveIndicator from '../components/LiveIndicator'
import {
  TIME_SERIES,
  CURRENT_CV_OBSERVATION,
  CURRENT_HEALTH,
} from '../data/mockData'

const PIPELINE_STATES = ['running', 'running', 'running', 'running', 'running', 'starting', 'reopening']

function nextPoint(prev) {
  const last = prev[prev.length - 1]
  const persons = Math.max(0, Math.min(8, last.persons + Math.round((Math.random() - 0.45) * 2)))
  const confidence_mean = persons > 0
    ? parseFloat(Math.min(0.99, 0.6 + Math.random() * 0.35).toFixed(3))
    : parseFloat((Math.random() * 0.3).toFixed(3))
  const pipeline_fps = parseFloat((28.5 + Math.random() * 1.7).toFixed(1))
  const inference_ms = parseFloat((10.5 + Math.random() * 6.3).toFixed(1))
  const now = new Date()
  return {
    ts: now.toISOString(),
    label: now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    persons,
    confidence_mean,
    pipeline_fps,
    inference_ms,
  }
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-slate-600 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <span className="font-bold">{p.value}</span> {p.unit ?? ''}
        </p>
      ))}
    </div>
  )
}

export default function LiveMetrics() {
  const [series, setSeries] = useState(TIME_SERIES.slice(-60))
  const [health, setHealth] = useState(CURRENT_HEALTH)
  const [lastUpdate, setLastUpdate] = useState(new Date())
  const [stateIdx, setStateIdx] = useState(0)
  const intervalRef = useRef(null)

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setSeries(prev => {
        const p = nextPoint(prev)
        const next = [...prev.slice(-89), p]
        return next
      })
      setStateIdx(i => (i + 1) % PIPELINE_STATES.length)
      setLastUpdate(new Date())
      setHealth(h => ({
        ...h,
        pipeline_state: PIPELINE_STATES[Math.floor(Math.random() * PIPELINE_STATES.length)],
        last_frame_ts: new Date().toISOString(),
      }))
    }, 2000)
    return () => clearInterval(intervalRef.current)
  }, [])

  const latest = series[series.length - 1]
  const displaySeries = series.slice(-30)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Live Metrics</h1>
          <p className="text-sm text-slate-500 mt-0.5">Real-time computer vision pipeline data</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <RefreshCw className="h-3 w-3 animate-spin" style={{ animationDuration: '2s' }} />
            Updated {lastUpdate.toLocaleTimeString()}
          </div>
          <LiveIndicator label="LIVE" />
        </div>
      </div>

      {/* Snapshot metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Person Count"
          value={latest?.persons ?? '—'}
          unit="persons"
          icon={Users}
          accent="indigo"
          subtext="Current window"
        />
        <MetricCard
          title="Confidence Mean"
          value={latest ? `${(latest.confidence_mean * 100).toFixed(0)}%` : '—'}
          icon={Gauge}
          accent={latest?.confidence_mean >= 0.7 ? 'green' : latest?.confidence_mean >= 0.5 ? 'amber' : 'red'}
          subtext={latest?.confidence_mean >= 0.7 ? 'High confidence' : latest?.confidence_mean >= 0.5 ? 'Medium confidence' : 'Low confidence'}
        />
        <MetricCard
          title="Pipeline FPS"
          value={latest?.pipeline_fps ?? '—'}
          unit="fps"
          icon={Activity}
          accent="green"
          subtext="Target: 30 fps"
        />
        <MetricCard
          title="Inference Latency"
          value={latest?.inference_ms ?? '—'}
          unit="ms"
          icon={Cpu}
          accent="blue"
          subtext="YOLOv8n"
        />
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Person Count chart */}
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">Person Count Over Time</h2>
            <StatusBadge variant="live" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={displaySeries} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="personGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                interval={Math.floor(displaySeries.length / 5)}
              />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} domain={[0, 10]} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="persons"
                name="Persons"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#personGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#6366f1' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Confidence Mean sparkline */}
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">Confidence Mean</h2>
            <StatusBadge variant="live" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={displaySeries} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                interval={Math.floor(displaySeries.length / 5)}
              />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="confidence_mean"
                name="Confidence"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#confGrad)"
                dot={false}
                activeDot={{ r: 4, fill: '#22c55e' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Pipeline FPS */}
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">Pipeline FPS</h2>
            <StatusBadge variant="live" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={displaySeries} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                interval={Math.floor(displaySeries.length / 5)}
              />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} domain={[25, 32]} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="pipeline_fps"
                name="FPS"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#3b82f6' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Inference latency */}
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">Inference Latency</h2>
            <StatusBadge variant="live" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={displaySeries} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                interval={Math.floor(displaySeries.length / 5)}
              />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} domain={[8, 20]} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="inference_ms"
                name="Latency (ms)"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#f59e0b' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Camera status card */}
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
        <div className="flex items-center gap-2 mb-4">
          <Camera className="h-4 w-4 text-indigo-500" />
          <h2 className="text-sm font-semibold text-slate-700">Camera Status — input-cv</h2>
          <StatusBadge variant={health.pipeline_state} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Device Path</p>
            <p className="font-mono text-sm font-semibold text-slate-800">{health.device_path}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Pipeline State</p>
            <StatusBadge variant={health.pipeline_state} />
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Device Present</p>
            <p className={`text-sm font-bold ${health.device_present ? 'text-green-600' : 'text-red-600'}`}>
              {health.device_present ? 'Yes' : 'No'}
            </p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">Reopen Count</p>
            <p className={`text-sm font-bold ${health.reopen_count > 0 ? 'text-amber-600' : 'text-slate-800'}`}>
              {health.reopen_count}
            </p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 sm:col-span-2">
            <p className="text-xs text-slate-500 mb-1">Last Frame Timestamp</p>
            <p className="font-mono text-xs text-slate-700">{health.last_frame_ts}</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3 sm:col-span-2">
            <p className="text-xs text-slate-500 mb-1">Pipeline Started</p>
            <p className="font-mono text-xs text-slate-700">{health.last_pipeline_start_ts}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
