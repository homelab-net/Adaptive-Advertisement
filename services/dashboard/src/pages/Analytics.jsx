import React from 'react'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { BarChart2, TrendingUp, Clock } from 'lucide-react'
import StubPage from '../components/StubPage'
import MetricCard from '../components/MetricCard'
import { ANALYTICS_SERIES } from '../data/mockData'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-slate-600 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <span className="font-bold">{typeof p.value === 'number' && p.value < 10 ? p.value.toFixed(1) : p.value}</span>
        </p>
      ))}
    </div>
  )
}

function WireframePreview() {
  const last14 = ANALYTICS_SERIES.slice(-14)
  const totalImpressions = ANALYTICS_SERIES.reduce((s, d) => s + d.impressions, 0)
  const avgDwell = (ANALYTICS_SERIES.reduce((s, d) => s + d.dwell_proxy, 0) / ANALYTICS_SERIES.length).toFixed(1)
  const avgAdaptiveCtr = (ANALYTICS_SERIES.reduce((s, d) => s + d.adaptive_ctr, 0) / ANALYTICS_SERIES.length).toFixed(2)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard title="Total Impressions" value={totalImpressions.toLocaleString()} icon={BarChart2} accent="indigo" subtext="Last 30 days" />
        <MetricCard title="Avg Dwell Proxy" value={avgDwell} unit="s" icon={Clock} accent="blue" subtext="Attention estimate" />
        <MetricCard title="Adaptive CTR" value={`${avgAdaptiveCtr}%`} icon={TrendingUp} accent="green" subtext="vs 1.4% static" />
      </div>

      {/* Impressions chart */}
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Impressions Over Time (30 days)</h3>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={ANALYTICS_SERIES} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="impGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} interval={4} />
            <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="impressions" name="Impressions" stroke="#6366f1" strokeWidth={2} fill="url(#impGrad)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Dwell proxy chart */}
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Dwell Time Proxy (last 14 days)</h3>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={last14} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="dwell_proxy" name="Dwell (s)" fill="#3b82f6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Static vs Adaptive CTR */}
      <div className="bg-white rounded-lg border border-slate-100 p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Static vs Adaptive CTR Comparison</h3>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={last14} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: '#94a3b8' }} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="static_ctr" name="Static CTR %" stroke="#94a3b8" strokeWidth={2} dot={false} strokeDasharray="4 2" />
            <Line type="monotone" dataKey="adaptive_ctr" name="Adaptive CTR %" stroke="#22c55e" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default function Analytics() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Analytics</h1>
        <p className="text-sm text-slate-500 mt-0.5">Impressions, dwell time proxy, and adaptive vs static performance</p>
      </div>
      <StubPage
        phase={7}
        title="Analytics Dashboard"
        description="Live impression tracking, dwell time analysis, and adaptive vs static performance comparison will be available once the analytics service is deployed in Phase 7."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
