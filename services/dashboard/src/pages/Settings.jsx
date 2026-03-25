import React from 'react'
import { Settings as SettingsIcon, Camera, Radio, Building2, Lock } from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import { SITE_CONFIG, CAMERA_SOURCE_CONFIG } from '../data/mockData'

function FieldRow({ label, value, mono = false, badge }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-slate-50 last:border-0">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <div className="flex items-center gap-2">
        {badge && <StatusBadge variant={badge} size="xs" />}
        <span className={`text-sm ${mono ? 'font-mono text-slate-700' : 'font-medium text-slate-800'}`}>
          {String(value)}
        </span>
      </div>
    </div>
  )
}

function Section({ icon: Icon, title, badge, children }) {
  return (
    <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
      <div className="flex items-center gap-2 mb-3 pb-3 border-b border-slate-100">
        <div className="bg-indigo-50 rounded-lg p-1.5">
          <Icon className="h-4 w-4 text-indigo-600" />
        </div>
        <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
        {badge && <StatusBadge variant={badge} size="xs" />}
      </div>
      {children}
    </div>
  )
}

export default function Settings() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Settings</h1>
          <p className="text-sm text-slate-500 mt-0.5">System configuration viewer — read-only in this phase</p>
        </div>
        <StatusBadge variant="stub" label="READ-ONLY STUB" />
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 flex items-center gap-3">
        <Lock className="h-4 w-4 text-amber-600 flex-shrink-0" />
        <p className="text-xs text-amber-800">
          Settings are read-only in this phase. Configuration is managed via on-device config files and environment variables. Write access will be available in a future phase.
        </p>
      </div>

      {/* Tenant / Site */}
      <Section icon={Building2} title="Tenant & Site Identity">
        <FieldRow label="Tenant ID" value={SITE_CONFIG.tenant_id} mono />
        <FieldRow label="Site ID" value={SITE_CONFIG.site_id} mono />
        <FieldRow label="Site Name" value={SITE_CONFIG.site_name} />
        <FieldRow label="Camera ID" value={SITE_CONFIG.camera_id} mono />
        <FieldRow label="Pipeline ID" value="pipeline_001" mono />
      </Section>

      {/* Camera config */}
      <Section icon={Camera} title="Camera Configuration" badge="live">
        <p className="text-xs text-slate-400 mb-3">Source: <span className="font-mono">camera-source.json</span></p>
        <FieldRow label="Camera ID" value={CAMERA_SOURCE_CONFIG.camera_id} mono />
        <FieldRow label="Device Path" value={CAMERA_SOURCE_CONFIG.device_path} mono />
        <FieldRow label="Resolution" value={`${CAMERA_SOURCE_CONFIG.resolution.width}×${CAMERA_SOURCE_CONFIG.resolution.height}`} mono />
        <FieldRow label="FPS Target" value={`${CAMERA_SOURCE_CONFIG.fps_target} fps`} mono />
        <FieldRow label="Inference Model" value={CAMERA_SOURCE_CONFIG.inference_model} mono />
        <FieldRow label="Window (ms)" value={`${CAMERA_SOURCE_CONFIG.window_ms} ms`} mono />
        <FieldRow label="Confidence Threshold" value={CAMERA_SOURCE_CONFIG.confidence_threshold} mono />
        <FieldRow label="Reopen Delay (ms)" value={`${CAMERA_SOURCE_CONFIG.reopen_delay_ms} ms`} mono />
        <FieldRow label="Max Reopen Attempts" value={CAMERA_SOURCE_CONFIG.max_reopen_attempts} mono />
      </Section>

      {/* MQTT config */}
      <Section icon={Radio} title="MQTT Broker Configuration" badge="live">
        <FieldRow label="Broker URL" value={SITE_CONFIG.mqtt_broker} mono />
        <FieldRow label="Topic Prefix" value={SITE_CONFIG.mqtt_topic_prefix} mono />
        <FieldRow label="Protocol" value="MQTT 3.1.1" mono />
        <FieldRow label="Implementation" value="Eclipse Mosquitto" />
        <FieldRow label="TLS" value="Disabled (local-only)" />
      </Section>

      {/* Privacy statement */}
      <div className="bg-slate-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <Lock className="h-4 w-4 text-green-400" />
          <h3 className="text-sm font-semibold text-white">Privacy Configuration</h3>
          <StatusBadge variant="online" label="VERIFIED" size="xs" />
        </div>
        <div className="space-y-1.5">
          {[
            ['contains_images', false],
            ['contains_frame_urls', false],
            ['contains_face_embeddings', false],
            ['biometric_data_collected', false],
            ['edge_processing_only', true],
          ].map(([key, val]) => (
            <div key={key} className="flex items-center justify-between text-xs">
              <span className="font-mono text-slate-400">{key}</span>
              <span className={`font-bold ${val ? 'text-green-400' : 'text-green-400'}`}>
                {String(val)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-400 border-t border-slate-700 pt-3">
          All CV outputs are count-only metadata. No pixel data, biometric data, or identifying information leaves the device.
        </p>
      </div>
    </div>
  )
}
