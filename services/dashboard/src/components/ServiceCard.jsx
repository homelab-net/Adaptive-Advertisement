import React from 'react'
import StatusBadge from './StatusBadge'
import { Server, Cpu, Radio, BarChart2, Film, Megaphone, Eye, PlayCircle } from 'lucide-react'

const SERVICE_ICONS = {
  'input-cv': Cpu,
  'audience-state': Eye,
  'player': PlayCircle,
  'decision-engine': BarChart2,
  'creative-manager': Film,
  'campaign-manager': Megaphone,
  'analytics': BarChart2,
  'mqtt-broker': Radio,
}

export default function ServiceCard({ service, healthData, compact = false }) {
  const Icon = SERVICE_ICONS[service.id] ?? Server
  const isOnline = service.status === 'online'
  const isInputCv = service.id === 'input-cv'

  if (compact) {
    return (
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-3 flex items-center gap-3">
        <div className={`flex-shrink-0 rounded-lg p-2 ${isOnline ? 'bg-green-50 text-green-600' : 'bg-slate-100 text-slate-400'}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-800 truncate">{service.name}</p>
          <p className="text-xs text-slate-500 truncate">{service.description}</p>
        </div>
        <StatusBadge variant={isOnline ? 'online' : 'offline'} />
      </div>
    )
  }

  return (
    <div className={`bg-white rounded-lg border shadow-sm p-4 ${isOnline ? 'border-green-200' : 'border-slate-100'}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div className={`flex-shrink-0 rounded-lg p-2 ${isOnline ? 'bg-green-50 text-green-600' : 'bg-slate-100 text-slate-400'}`}>
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">{service.name}</p>
            <p className="text-xs text-slate-500">Phase {service.phase}</p>
          </div>
        </div>
        <StatusBadge variant={isOnline ? 'online' : 'offline'} />
      </div>

      <p className="text-xs text-slate-500 mb-3">{service.description}</p>

      {isInputCv && isOnline && healthData ? (
        <div className="space-y-1.5 border-t border-slate-100 pt-3">
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Pipeline State</span>
            <StatusBadge variant={healthData.pipeline_state} size="xs" />
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Device</span>
            <span className="font-mono text-slate-700">{healthData.device_path}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Device Present</span>
            <span className={`font-semibold ${healthData.device_present ? 'text-green-600' : 'text-red-600'}`}>
              {healthData.device_present ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Reopen Count</span>
            <span className={`font-semibold ${healthData.reopen_count > 0 ? 'text-amber-600' : 'text-slate-700'}`}>
              {healthData.reopen_count}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-slate-500">Last Frame</span>
            <span className="text-slate-600">{new Date(healthData.last_frame_ts).toLocaleTimeString()}</span>
          </div>
        </div>
      ) : !isOnline ? (
        <div className="border-t border-slate-100 pt-3">
          <p className="text-xs text-slate-400 italic">Service offline — not deployed</p>
        </div>
      ) : null}
    </div>
  )
}
