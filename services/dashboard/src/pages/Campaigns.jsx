import React from 'react'
import { Megaphone, Calendar, TrendingUp } from 'lucide-react'
import StubPage from '../components/StubPage'
import StatusBadge from '../components/StatusBadge'
import { CAMPAIGNS } from '../data/mockData'

const STATUS_VARIANT = {
  active: 'active',
  paused: 'paused',
  pending_approval: 'pending_approval',
}

function WireframePreview() {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100">
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Campaign</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Status</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3 hidden sm:table-cell">Schedule</th>
              <th className="text-right text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3 hidden md:table-cell">Impressions</th>
              <th className="text-right text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Budget</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {CAMPAIGNS.map(camp => (
              <tr key={camp.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 bg-indigo-50 rounded flex items-center justify-center flex-shrink-0">
                      <Megaphone className="h-3.5 w-3.5 text-indigo-500" />
                    </div>
                    <div>
                      <p className="font-medium text-slate-800">{camp.name}</p>
                      <p className="text-xs text-slate-400 font-mono">{camp.id}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={STATUS_VARIANT[camp.status] ?? 'stub'} size="xs" />
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <div className="flex items-center gap-1 text-xs text-slate-600">
                    <Calendar className="h-3 w-3 text-slate-400" />
                    {camp.start_date} → {camp.end_date}
                  </div>
                </td>
                <td className="px-4 py-3 text-right hidden md:table-cell">
                  <div className="flex items-center justify-end gap-1 text-xs text-slate-700">
                    <TrendingUp className="h-3 w-3 text-slate-400" />
                    {camp.impressions.toLocaleString()}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="text-sm font-semibold text-slate-800">£{camp.budget.toLocaleString()}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mock schedule view */}
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm p-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Schedule View (Week)</h3>
        <div className="grid grid-cols-7 gap-1 text-center">
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => (
            <div key={day} className="text-xs text-slate-500 font-medium pb-1">{day}</div>
          ))}
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, i) => (
            <div key={day} className={`rounded py-3 text-xs font-medium ${
              i < 5
                ? 'bg-indigo-100 text-indigo-700'
                : 'bg-slate-100 text-slate-400'
            }`}>
              {i < 5 ? '2 active' : '—'}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function Campaigns() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Campaigns</h1>
        <p className="text-sm text-slate-500 mt-0.5">Campaign scheduling, budgets, and performance</p>
      </div>
      <StubPage
        phase={7}
        title="Campaign Management"
        description="Full campaign creation, scheduling, budget management, and approval workflows will be available once the campaign-manager service is deployed in Phase 7."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
