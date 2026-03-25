import React from 'react'
import { MapPin, Wifi, WifiOff } from 'lucide-react'
import { SITE_CONFIG, SERVICES } from '../data/mockData'
import LiveIndicator from './LiveIndicator'

export default function TopBar({ health }) {
  const mqttOnline = SERVICES.find(s => s.id === 'mqtt-broker')?.status === 'online'
  const cvOnline = SERVICES.find(s => s.id === 'input-cv')?.status === 'online'
  const pipelineState = health?.pipeline_state ?? 'unknown'

  return (
    <header className="flex items-center gap-4 bg-white border-b border-slate-200 px-4 h-[60px] flex-shrink-0">
      {/* Site info */}
      <div className="flex items-center gap-1.5 text-sm text-slate-600">
        <MapPin className="h-4 w-4 text-indigo-500" />
        <span className="font-semibold text-slate-800">{SITE_CONFIG.site_name}</span>
        <span className="text-slate-400">·</span>
        <span className="text-slate-500 font-mono text-xs">{SITE_CONFIG.site_id}</span>
      </div>

      <div className="flex-1" />

      {/* Status pills */}
      <div className="flex items-center gap-2">
        {/* MQTT */}
        <div className={`flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-1 border ${
          mqttOnline
            ? 'bg-green-50 text-green-700 border-green-200'
            : 'bg-slate-50 text-slate-400 border-slate-200'
        }`}>
          {mqttOnline ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
          MQTT
        </div>

        {/* CV pipeline */}
        {cvOnline ? (
          <div className="flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-1 bg-green-50 text-green-700 border border-green-200">
            <LiveIndicator label={`CV · ${pipelineState.toUpperCase()}`} />
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-xs font-medium rounded-full px-2.5 py-1 bg-slate-50 text-slate-400 border border-slate-200">
            CV · OFFLINE
          </div>
        )}
      </div>
    </header>
  )
}
