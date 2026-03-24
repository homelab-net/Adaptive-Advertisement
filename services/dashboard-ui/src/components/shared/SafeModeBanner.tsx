import { AlertTriangle, X } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { SafeModeInfo } from '@/types/api'

interface SafeModeBannerProps {
  safeMode: SafeModeInfo
}

export function SafeModeBanner({ safeMode }: SafeModeBannerProps) {
  const qc = useQueryClient()
  const clear = useMutation({
    mutationFn: api.system.clearSafeMode,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['system-status'] })
      qc.invalidateQueries({ queryKey: ['safe-mode'] })
    },
  })

  if (!safeMode.active) return null

  return (
    <div className="flex items-center justify-between bg-amber-50 border-b border-amber-200 px-6 py-2.5 text-sm text-amber-800">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 flex-shrink-0 text-amber-600" />
        <span className="font-medium">Safe Mode Active</span>
        {safeMode.reason && (
          <span className="text-amber-700">— {safeMode.reason}</span>
        )}
      </div>
      <button
        onClick={() => clear.mutate()}
        disabled={clear.isPending}
        className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 transition-colors disabled:opacity-50"
      >
        <X className="h-3 w-3" />
        Clear
      </button>
    </div>
  )
}
