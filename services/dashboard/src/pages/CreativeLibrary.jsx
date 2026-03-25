import React from 'react'
import { Film, Upload, Tag } from 'lucide-react'
import StubPage from '../components/StubPage'
import StatusBadge from '../components/StatusBadge'
import { CREATIVE_ASSETS } from '../data/mockData'

const TYPE_LABELS = { template: 'Template', headline: 'Headline', cta: 'CTA' }
const TYPE_COLORS = {
  template: 'bg-blue-50 text-blue-700',
  headline: 'bg-purple-50 text-purple-700',
  cta: 'bg-indigo-50 text-indigo-700',
}

function WireframePreview() {
  return (
    <div className="space-y-4">
      {/* Upload button (disabled) */}
      <div className="flex justify-end">
        <button
          disabled
          className="flex items-center gap-2 bg-indigo-100 text-indigo-400 font-medium text-sm rounded-lg px-4 py-2 cursor-not-allowed"
        >
          <Upload className="h-4 w-4" />
          Upload Creative
        </button>
      </div>

      {/* Creative list */}
      <div className="bg-white rounded-lg border border-slate-100 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-100">
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Name</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Type</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3 hidden sm:table-cell">Dimensions</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3 hidden sm:table-cell">Duration</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3">Status</th>
              <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide px-4 py-3 hidden lg:table-cell">Tags</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {CREATIVE_ASSETS.map(asset => (
              <tr key={asset.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-slate-100 rounded flex items-center justify-center flex-shrink-0">
                      <Film className="h-4 w-4 text-slate-400" />
                    </div>
                    <div>
                      <p className="font-medium text-slate-800">{asset.name}</p>
                      <p className="text-xs text-slate-400 font-mono">{asset.id}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center text-xs font-medium rounded-full px-2 py-0.5 ${TYPE_COLORS[asset.type] ?? 'bg-slate-50 text-slate-600'}`}>
                    {TYPE_LABELS[asset.type] ?? asset.type}
                  </span>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <span className="font-mono text-xs text-slate-600">{asset.dimensions}</span>
                </td>
                <td className="px-4 py-3 hidden sm:table-cell">
                  <span className="text-xs text-slate-600">{asset.duration_s}s</span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={asset.status} size="xs" />
                </td>
                <td className="px-4 py-3 hidden lg:table-cell">
                  <div className="flex flex-wrap gap-1">
                    {asset.tags.map(tag => (
                      <span key={tag} className="inline-flex items-center gap-0.5 text-xs bg-slate-100 text-slate-500 rounded px-1.5 py-0.5">
                        <Tag className="h-2.5 w-2.5" />
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function CreativeLibrary() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Creative Library</h1>
        <p className="text-sm text-slate-500 mt-0.5">Ad creative assets, templates, and approval workflow</p>
      </div>
      <StubPage
        phase={5}
        title="Creative Asset Library"
        description="Full creative management, upload, approval workflow, and template editor will be available once the creative-manager service is deployed in Phase 5."
      >
        <WireframePreview />
      </StubPage>
    </div>
  )
}
