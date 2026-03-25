import React from 'react'

export default function MetricCard({
  title,
  value,
  unit = '',
  subtext,
  icon: Icon,
  accent = 'indigo',
  trend,
  className = '',
}) {
  const accentMap = {
    indigo: 'bg-indigo-50 text-indigo-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    slate: 'bg-slate-100 text-slate-600',
    blue: 'bg-blue-50 text-blue-600',
  }
  const iconBg = accentMap[accent] ?? accentMap.indigo

  return (
    <div className={`bg-white rounded-lg shadow-sm border border-slate-100 p-4 flex items-start gap-3 ${className}`}>
      {Icon && (
        <div className={`flex-shrink-0 rounded-lg p-2.5 ${iconBg}`}>
          <Icon className="h-5 w-5" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide truncate">{title}</p>
        <p className="mt-0.5 text-2xl font-bold text-slate-900 leading-none">
          {value}
          {unit && <span className="ml-1 text-base font-medium text-slate-500">{unit}</span>}
        </p>
        {subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}
        {trend !== undefined && (
          <p className={`mt-1 text-xs font-medium ${trend >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}% vs prev window
          </p>
        )}
      </div>
    </div>
  )
}
