import { Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Sidebar } from './Sidebar'
import { SafeModeBanner } from '@/components/shared/SafeModeBanner'
import { api } from '@/lib/api'

export function Layout() {
  // Poll safe-mode state every 15s so the banner stays in sync
  const { data: safeMode } = useQuery({
    queryKey: ['safe-mode'],
    queryFn: api.system.safeMode,
    refetchInterval: 15_000,
    staleTime: 10_000,
  })

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {safeMode && <SafeModeBanner safeMode={safeMode} />}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
