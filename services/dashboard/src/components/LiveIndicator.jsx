import React from 'react'

export default function LiveIndicator({ label = 'LIVE', className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold text-green-700 ${className}`}>
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      {label}
    </span>
  )
}
