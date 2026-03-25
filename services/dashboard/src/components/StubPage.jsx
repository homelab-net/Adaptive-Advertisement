import React from 'react'
import { Clock } from 'lucide-react'

export default function StubPage({ phase, title, description, children }) {
  return (
    <div className="space-y-6">
      {/* Phase banner */}
      <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
        <Clock className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">
            Phase {phase} — Not yet built
          </p>
          <p className="text-xs text-amber-700 mt-0.5">
            This feature is planned for Phase {phase}. The wireframe below shows what will be available when it ships.
          </p>
        </div>
        <span className="ml-auto flex-shrink-0 inline-flex items-center rounded-full bg-amber-100 border border-amber-300 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
          PHASE {phase} STUB
        </span>
      </div>

      {/* Wireframe preview area */}
      <div className="relative">
        {/* Overlay blur hint */}
        <div className="absolute inset-0 z-10 rounded-xl pointer-events-none border-2 border-dashed border-amber-300" />
        <div className="opacity-40 pointer-events-none select-none">
          {children}
        </div>
        <div className="absolute inset-0 z-20 flex items-center justify-center">
          <div className="bg-white/90 backdrop-blur-sm rounded-xl px-6 py-4 text-center shadow-lg border border-amber-200">
            <p className="text-lg font-bold text-slate-700">{title}</p>
            <p className="text-sm text-slate-500 mt-1 max-w-sm">{description}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
