import React from 'react'

const VARIANTS = {
  live: 'bg-green-100 text-green-800 border border-green-200',
  online: 'bg-green-100 text-green-800 border border-green-200',
  stub: 'bg-amber-100 text-amber-800 border border-amber-200',
  offline: 'bg-slate-100 text-slate-500 border border-slate-200',
  error: 'bg-red-100 text-red-700 border border-red-200',
  failed: 'bg-red-100 text-red-700 border border-red-200',
  warning: 'bg-amber-100 text-amber-700 border border-amber-200',
  running: 'bg-green-100 text-green-800 border border-green-200',
  starting: 'bg-blue-100 text-blue-700 border border-blue-200',
  reopening: 'bg-amber-100 text-amber-700 border border-amber-200',
  approved: 'bg-green-100 text-green-800 border border-green-200',
  pending: 'bg-amber-100 text-amber-700 border border-amber-200',
  rejected: 'bg-red-100 text-red-700 border border-red-200',
  active: 'bg-green-100 text-green-800 border border-green-200',
  paused: 'bg-slate-100 text-slate-600 border border-slate-200',
  pending_approval: 'bg-amber-100 text-amber-700 border border-amber-200',
}

const LABELS = {
  live: 'LIVE',
  online: 'ONLINE',
  stub: 'PLACEHOLDER',
  offline: 'OFFLINE',
  error: 'ERROR',
  failed: 'FAILED',
  warning: 'WARNING',
  running: 'RUNNING',
  starting: 'STARTING',
  reopening: 'REOPENING',
  approved: 'APPROVED',
  pending: 'PENDING',
  rejected: 'REJECTED',
  active: 'ACTIVE',
  paused: 'PAUSED',
  pending_approval: 'PENDING APPROVAL',
}

export default function StatusBadge({ variant = 'stub', label, size = 'sm' }) {
  const cls = VARIANTS[variant] ?? VARIANTS.stub
  const text = label ?? LABELS[variant] ?? variant.toUpperCase()
  const sizeClass = size === 'xs' ? 'text-xs px-1.5 py-0.5' : 'text-xs px-2 py-0.5'

  return (
    <span className={`inline-flex items-center rounded-full font-semibold tracking-wide ${sizeClass} ${cls}`}>
      {(variant === 'live' || variant === 'online' || variant === 'running') && (
        <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
      )}
      {text}
    </span>
  )
}
