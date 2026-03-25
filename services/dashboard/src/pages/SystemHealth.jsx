import React, { useState, useEffect } from 'react'
import { HeartPulse, Radio, Clock } from 'lucide-react'
import ServiceCard from '../components/ServiceCard'
import StatusBadge from '../components/StatusBadge'
import LiveIndicator from '../components/LiveIndicator'
import {
  SERVICES,
  CURRENT_HEALTH,
  SYSTEM_UPTIME_SECONDS,
  formatUptime,
} from '../data/mockData'

const PIPELINE_STATES = ['running', 'running', 'running', 'running', 'running', 'starting', 'reopening']

export default function SystemHealth() {
  const [health, setHealth] = useState(CURRENT_HEALTH)
  const [uptime, setUptime] = useState(SYSTEM_UPTIME_SECONDS)

  useEffect(() => {
    const iv = setInterval(() => {
      setHealth(h => ({
        ...h,
        pipeline_state: PIPELINE_STATES[Math.floor(Math.random() * PIPELINE_STATES.length)],
        last_frame_ts: new Date().toISOString(),
      }))
      setUptime(u => u + 5)
    }, 5000)
    return () => clearInterval(iv)
  }, [])

  const onlineCount = SERVICES.filter(s => s.status === 'online').length
  const mqttService = SERVICES.find(s => s.id === 'mqtt-broker')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">System Health</h1>
          <p className="text-sm text-slate-500 mt-0.5">Service status, pipeline health, and system uptime</p>
        </div>
        <LiveIndicator label="PARTIAL LIVE" />
      </div>

      {/* Top summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4 flex items-start gap-3">
          <div className="bg-green-50 rounded-lg p-2.5 flex-shrink-0">
            <HeartPulse className="h-5 w-5 text-green-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">Services Online</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">
              {onlineCount}
              <span className="text-base font-medium text-slate-500 ml-1">/ {SERVICES.length}</span>
            </p>
            <p className="text-xs text-slate-500 mt-1">Phase 1 services active</p>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4 flex items-start gap-3">
          <div className="bg-indigo-50 rounded-lg p-2.5 flex-shrink-0">
            <Clock className="h-5 w-5 text-indigo-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">System Uptime</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">{formatUptime(uptime)}</p>
            <p className="text-xs text-slate-500 mt-1">Since last restart</p>
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4 flex items-start gap-3">
          <div className={`rounded-lg p-2.5 flex-shrink-0 ${mqttService?.status === 'online' ? 'bg-green-50' : 'bg-slate-100'}`}>
            <Radio className={`h-5 w-5 ${mqttService?.status === 'online' ? 'text-green-600' : 'text-slate-400'}`} />
          </div>
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">MQTT Broker</p>
            <p className="text-2xl font-bold text-slate-900 mt-0.5">
              {mqttService?.status === 'online' ? 'Online' : 'Offline'}
            </p>
            <p className="text-xs text-slate-500 mt-1">mqtt://localhost:1883</p>
          </div>
        </div>
      </div>

      {/* Service grid */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">All Services</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {SERVICES.map(service => (
            <ServiceCard
              key={service.id}
              service={service}
              healthData={service.id === 'input-cv' ? health : null}
            />
          ))}
        </div>
      </div>

      {/* MQTT detail */}
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
        <div className="flex items-center gap-2 mb-3">
          <Radio className="h-4 w-4 text-indigo-500" />
          <h2 className="text-sm font-semibold text-slate-700">MQTT Broker Detail</h2>
          <StatusBadge variant={mqttService?.status === 'online' ? 'online' : 'offline'} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Broker</p>
            <p className="font-mono text-sm text-slate-700 mt-0.5">localhost:1883</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Protocol</p>
            <p className="font-mono text-sm text-slate-700 mt-0.5">MQTT 3.1.1</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Topic Prefix</p>
            <p className="font-mono text-xs text-slate-700 mt-0.5">adv/tenant_001/site_pilot_01</p>
          </div>
          <div className="bg-slate-50 rounded-lg p-3">
            <p className="text-xs text-slate-500">Implementation</p>
            <p className="font-mono text-sm text-slate-700 mt-0.5">Mosquitto</p>
          </div>
        </div>
      </div>
    </div>
  )
}
