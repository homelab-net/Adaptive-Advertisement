import { useQuery } from '@tanstack/react-query'
import { RefreshCw, CheckCircle2, AlertCircle, XCircle, Clock, Wifi } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate, cn } from '@/lib/utils'
import type { ServiceHealth, OverallHealth } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

function HealthIcon({ status }: { status: ServiceHealth | OverallHealth }) {
  if (status === 'healthy')    return <CheckCircle2 className="h-4 w-4 text-emerald-500" />
  if (status === 'degraded')   return <AlertCircle className="h-4 w-4 text-amber-500" />
  if (status === 'critical')   return <AlertCircle className="h-4 w-4 text-red-500" />
  if (status === 'unhealthy')  return <XCircle className="h-4 w-4 text-red-500" />
  return <XCircle className="h-4 w-4 text-zinc-400" />
}

function HealthDot({ status }: { status: ServiceHealth }) {
  return (
    <span className={cn(
      'inline-block h-2.5 w-2.5 rounded-full flex-shrink-0',
      status === 'healthy'    ? 'bg-emerald-500' :
      status === 'unhealthy'  ? 'bg-red-500' :
                                'bg-zinc-400'
    )} />
  )
}

const SERVICE_LABELS: Record<string, string> = {
  'player':             'Player',
  'audience-state':     'Audience State',
  'decision-optimizer': 'Decision Engine',
  'creative':           'Creative',
}

export function SystemPage() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['system-status'],
    queryFn: api.system.status,
    refetchInterval: 30_000,
    staleTime: 20_000,
  })

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">System Status</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Live health across all appliance services
            {dataUpdatedAt > 0 && (
              <span className="ml-2 text-xs">— last checked {new Date(dataUpdatedAt).toLocaleTimeString()}</span>
            )}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Overall status banner */}
      {data && (
        <div className={cn(
          'flex items-center gap-3 rounded-lg border p-4 mb-6',
          data.overall === 'healthy'  ? 'bg-emerald-50 border-emerald-200' :
          data.overall === 'degraded' ? 'bg-amber-50 border-amber-200' :
                                        'bg-red-50 border-red-200'
        )}>
          <HealthIcon status={data.overall} />
          <div>
            <p className={cn(
              'text-sm font-semibold capitalize',
              data.overall === 'healthy'  ? 'text-emerald-800' :
              data.overall === 'degraded' ? 'text-amber-800' : 'text-red-800'
            )}>
              {data.overall === 'healthy' ? 'All systems operational' :
               data.overall === 'degraded' ? 'Partial degradation — playback unaffected' :
               'Critical — check player service'}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">Sampled {formatDate(data.sampled_at)}</p>
          </div>
        </div>
      )}

      {/* Services grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {isLoading && Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="h-16 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
        {data && Object.entries(data.services).map(([name, probe]) => (
          <Card key={name}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">{SERVICE_LABELS[name] ?? name}</CardTitle>
                <HealthDot status={probe.status} />
              </div>
            </CardHeader>
            <CardContent>
              <p className={cn(
                'text-2xl font-bold capitalize',
                probe.status === 'healthy' ? 'text-emerald-600' :
                probe.status === 'unhealthy' ? 'text-red-600' : 'text-zinc-400'
              )}>
                {probe.status}
              </p>
              {probe.latency_ms != null && (
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <Clock className="h-3 w-3" />{probe.latency_ms} ms
                </p>
              )}
              {probe.detail && (
                <p className="text-xs text-muted-foreground mt-1 truncate">{probe.detail}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Safe mode state */}
      {data && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Wifi className="h-4 w-4" />
              Safe Mode
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant={data.safe_mode.active ? 'rejected' : 'enabled'}>
                  {data.safe_mode.active ? 'Active' : 'Inactive'}
                </Badge>
                {data.safe_mode.reason && (
                  <span className="text-sm text-muted-foreground">{data.safe_mode.reason}</span>
                )}
                {data.safe_mode.activated_at && (
                  <span className="text-xs text-muted-foreground">since {formatDate(data.safe_mode.activated_at)}</span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
