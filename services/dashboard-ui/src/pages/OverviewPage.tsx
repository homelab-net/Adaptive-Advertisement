import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users, Activity, WifiOff, AlertTriangle, ShieldAlert, ShieldCheck,
  RefreshCw, Eye, Zap, Timer, Radio,
} from 'lucide-react'
import { api } from '@/lib/api'
import type { SafeModeInfo, LiveStatus, SystemStatus } from '@/types/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { cn, formatDate } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SERVICE_LABELS: Record<string, string> = {
  'player':             'Player',
  'audience-state':     'Audience State',
  'decision-optimizer': 'Decision Engine',
  'creative':           'Creative',
}

function playerStateBadgeVariant(state: string | null | undefined): string {
  switch (state) {
    case 'active':    return 'enabled'
    case 'fallback':  return 'paused'
    case 'frozen':    return 'frozen'
    case 'safe_mode': return 'rejected'
    default:          return 'default'
  }
}

function playerStateAccentClass(state: string | null | undefined): string {
  switch (state) {
    case 'active':    return 'bg-emerald-500'
    case 'fallback':  return 'bg-amber-500'
    case 'frozen':    return 'bg-blue-500'
    case 'safe_mode': return 'bg-red-500'
    default:          return 'bg-zinc-400'
  }
}

const AGE_GROUP_COLORS: Record<string, string> = {
  child:       'bg-blue-400',
  young_adult: 'bg-emerald-400',
  adult:       'bg-violet-400',
  senior:      'bg-amber-400',
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DiagnosticCanvas({ live }: { live: LiveStatus | undefined }) {
  const cv = live?.cv

  const isOffline = !cv || !cv.available
  const isStale = !isOffline && (cv?.signal_age_ms ?? 0) > 5000

  if (isOffline) {
    return (
      <div className={cn(
        'relative bg-zinc-900 rounded-lg overflow-hidden flex flex-col items-center justify-center',
        'border-2 border-dashed border-amber-500/40',
      )} style={{ minHeight: 280 }}>
        <WifiOff className="h-8 w-8 text-zinc-500 mb-3" />
        <p className="text-zinc-400 font-medium text-sm">CV pipeline offline</p>
        {/* PLACEHOLDER: populates when input-cv and audience-state are running on Jetson hardware */}
        <p className="text-zinc-600 text-xs mt-2 max-w-xs text-center px-4">
          PLACEHOLDER: populates when input-cv and audience-state are running on Jetson hardware
        </p>
      </div>
    )
  }

  const personCount = Math.min(cv!.count ?? 0, 8)
  const demographics = cv!.demographics

  return (
    <div
      className={cn(
        'relative bg-zinc-900 rounded-lg overflow-hidden',
        cv!.freeze_decision && 'ring-2 ring-amber-500',
        isStale && 'border-2 border-amber-500 animate-pulse',
      )}
      style={{ minHeight: 280 }}
    >
      {/* Dot grid background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(circle, #3f3f46 1px, transparent 1px)',
          backgroundSize: '32px 32px',
        }}
      />

      {/* Person silhouette area */}
      <div className="relative z-10 flex flex-col items-center pt-8 pb-4">
        {personCount === 0 ? (
          <p className="text-zinc-500 text-sm mt-6 mb-4">No audience detected</p>
        ) : (
          <div className="flex gap-3 justify-center items-end flex-wrap px-6">
            {Array.from({ length: personCount }).map((_, i) => (
              <Users key={i} className="h-10 w-10 text-zinc-300" />
            ))}
          </div>
        )}
        <p className="text-zinc-400 text-sm mt-2">
          {cv!.count ?? 0} person{(cv!.count ?? 0) !== 1 ? 's' : ''} detected
        </p>

        {isStale && (
          <p className="text-amber-400 text-xs mt-1 font-medium">&#9888; Signal stale</p>
        )}
      </div>

      {/* Metadata strip */}
      <div className="absolute bottom-0 left-0 right-0 bg-zinc-900/90 backdrop-blur px-4 py-2">
        {/* Primary metrics row */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400 mb-1.5">
          <span className="flex items-center gap-1">
            <Eye className="h-3 w-3" />
            {cv!.confidence != null ? `${(cv!.confidence * 100).toFixed(0)}%` : '—'} conf
          </span>
          <span className="flex items-center gap-1">
            <Zap className="h-3 w-3" />
            {cv!.fps != null ? `${cv!.fps.toFixed(1)}` : '—'} fps
          </span>
          <span className="flex items-center gap-1">
            <Timer className="h-3 w-3" />
            {cv!.inference_ms != null ? `${cv!.inference_ms}` : '—'} ms
          </span>
          <span className="flex items-center gap-1">
            <Radio className="h-3 w-3" />
            {cv!.signal_age_ms != null ? `${cv!.signal_age_ms}ms` : '—'} ago
          </span>

          {/* Stability indicator */}
          <span className={cn(
            'font-medium',
            cv!.state_stable ? 'text-emerald-400' : 'text-amber-400',
          )}>
            {cv!.state_stable != null ? (cv!.state_stable ? 'STABLE' : 'UNSTABLE') : '—'}
          </span>

          {/* Freeze gate */}
          <span className={cn(
            'font-medium',
            cv!.freeze_decision ? 'text-amber-400' : 'text-zinc-500',
          )}>
            {cv!.freeze_decision ? '⚠ FREEZE GATE ON' : 'FREEZE GATE OFF'}
          </span>
        </div>

        {/* Demographic bar */}
        {demographics && !demographics.suppressed && demographics.age_group && (
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-zinc-500 shrink-0">Age:</span>
            <div className="flex gap-0.5 flex-1 h-2 rounded-full overflow-hidden">
              {(['child', 'young_adult', 'adult', 'senior'] as const).map((group) => {
                const pct = demographics.age_group![group] ?? 0
                if (pct === 0) return null
                return (
                  <div
                    key={group}
                    className={cn('rounded-full h-2 inline-block', AGE_GROUP_COLORS[group])}
                    style={{ width: `${Math.max(pct, 2)}%` }}
                    title={`${group}: ${pct.toFixed(0)}%`}
                  />
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Privacy badge */}
      <div className="absolute bottom-2 right-2 text-zinc-600 text-xs pointer-events-none">
        &#128274; Metadata only — no images
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Safe Mode AlertDialogs
// ---------------------------------------------------------------------------

function EngageSafeModeDialog({
  onConfirm,
  isPending,
}: {
  onConfirm: (reason: string) => void
  isPending: boolean
}) {
  const [reason, setReason] = useState('')

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline-destructive" size="sm">
          <ShieldAlert className="h-3.5 w-3.5" />
          Engage Safe Mode
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Engage Safe Mode?</AlertDialogTitle>
          <AlertDialogDescription>
            This will halt adaptive playback and force the player into its safe fallback state.
            All audience-targeted content will stop until safe mode is cleared.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-2">
          <Label htmlFor="safe-mode-reason" className="text-sm font-medium mb-1.5 block">
            Reason
          </Label>
          <Textarea
            id="safe-mode-reason"
            placeholder="Enter reason for engaging safe mode…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-red-600 hover:bg-red-700 text-white"
            onClick={() => onConfirm(reason)}
            disabled={isPending}
          >
            {isPending ? 'Engaging…' : 'Engage Safe Mode'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function ClearSafeModeDialog({
  onConfirm,
  isPending,
}: {
  onConfirm: () => void
  isPending: boolean
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline-success" size="sm">
          <ShieldCheck className="h-3.5 w-3.5" />
          Clear Safe Mode
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Clear Safe Mode?</AlertDialogTitle>
          <AlertDialogDescription>
            This will re-enable adaptive playback. The player will resume audience-targeted content
            from the active manifest.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending ? 'Clearing…' : 'Clear Safe Mode'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ---------------------------------------------------------------------------
// Player State Card
// ---------------------------------------------------------------------------

function PlayerStateCard({
  live,
  onEngageSafeMode,
  onClearSafeMode,
  engagePending,
  clearPending,
}: {
  live: LiveStatus | undefined
  onEngageSafeMode: (reason: string) => void
  onClearSafeMode: () => void
  engagePending: boolean
  clearPending: boolean
}) {
  const player = live?.player
  const isOffline = !player || !player.available

  return (
    <Card className="mb-6 overflow-hidden">
      <div className="flex">
        {/* Left accent bar */}
        <div
          className={cn(
            'w-1 rounded-l shrink-0',
            isOffline ? 'bg-zinc-400' : playerStateAccentClass(player?.state),
          )}
        />

        <div className="flex-1 pl-4">
          <CardHeader className="pb-2 flex-row items-start justify-between space-y-0">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              Player State
            </CardTitle>

            {/* Safe mode action button */}
            {!isOffline && (
              <div>
                {player!.state === 'safe_mode' ? (
                  <ClearSafeModeDialog onConfirm={onClearSafeMode} isPending={clearPending} />
                ) : (
                  <EngageSafeModeDialog onConfirm={onEngageSafeMode} isPending={engagePending} />
                )}
              </div>
            )}
          </CardHeader>

          <CardContent className="pt-0">
            {isOffline ? (
              <div className="flex flex-col gap-1 py-2">
                <div className="flex items-center gap-2 text-zinc-500">
                  <WifiOff className="h-4 w-4" />
                  <span className="text-sm font-medium">Player offline</span>
                </div>
                {/* PLACEHOLDER: /api/v1/live not yet built — player state will show here once endpoint is available */}
                <p className="text-xs text-zinc-500 mt-1">
                  PLACEHOLDER: /api/v1/live not yet built — player state will show here once endpoint is available
                </p>
              </div>
            ) : (
              <div className="space-y-2 py-1">
                {/* State */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-16 shrink-0">State</span>
                  <Badge variant={playerStateBadgeVariant(player!.state)}>
                    {player!.state ?? '—'}
                  </Badge>
                </div>

                {/* Manifest */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-16 shrink-0">Manifest</span>
                  <code className="text-xs font-mono text-zinc-700 dark:text-zinc-300 truncate max-w-xs">
                    {player!.active_manifest_id ?? '—'}
                  </code>
                </div>

                {/* Rule / reason */}
                {(player!.freeze_reason || player!.safe_mode_reason) && (
                  <div className="flex items-start gap-2">
                    <span className="text-xs text-muted-foreground w-16 shrink-0 pt-0.5">Rule</span>
                    <span className="text-xs text-zinc-600 dark:text-zinc-400">
                      {player!.freeze_reason ?? player!.safe_mode_reason}
                    </span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Safe Mode Active Banner
// ---------------------------------------------------------------------------

function SafeModeBanner({
  safeMode,
  onClear,
  isPending,
}: {
  safeMode: SafeModeInfo
  onClear: () => void
  isPending: boolean
}) {
  if (!safeMode.active) return null

  return (
    <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 mb-6 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">Safe Mode Active</p>
          {safeMode.reason && (
            <p className="text-sm text-amber-700 mt-0.5">{safeMode.reason}</p>
          )}
          {safeMode.activated_at && (
            <p className="text-xs text-amber-600 mt-1">
              Activated {formatDate(safeMode.activated_at)}
            </p>
          )}
        </div>
      </div>
      <ClearSafeModeDialog onConfirm={onClear} isPending={isPending} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Service Health Grid
// ---------------------------------------------------------------------------

function ServiceHealthGrid({ sysStatus }: { sysStatus: SystemStatus | undefined }) {
  if (!sysStatus) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-12 rounded bg-zinc-100 animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {Object.entries(sysStatus.services).map(([name, probe]) => (
        <div
          key={name}
          className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2.5"
        >
          <span className="text-xs font-medium text-muted-foreground truncate">
            {SERVICE_LABELS[name] ?? name}
          </span>
          <Badge
            variant={
              probe.status === 'healthy' ? 'enabled' :
              probe.status === 'unhealthy' ? 'rejected' :
              'paused'
            }
            className="ml-2 shrink-0"
          >
            {probe.status}
          </Badge>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function OverviewPage() {
  const queryClient = useQueryClient()

  // Live view: PLACEHOLDER — /api/v1/live not yet built.
  // api.live.status() catches 404 and returns { cv: null, player: null }.
  const { data: live, refetch: refetchLive } = useQuery({
    queryKey: ['live'],
    queryFn: api.live.status,
    refetchInterval: 2_000,
  })

  // System status for safe mode + service health
  const { data: sysStatus } = useQuery({
    queryKey: ['system-status'],
    queryFn: api.system.status,
    refetchInterval: 15_000,
  })

  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['system-status'] })
    queryClient.invalidateQueries({ queryKey: ['live'] })
  }

  const engageSafeMode = useMutation({
    mutationFn: (reason: string) => api.system.engageSafeMode(reason),
    onSuccess: invalidateQueries,
  })

  const clearSafeMode = useMutation({
    mutationFn: () => api.system.clearSafeMode(),
    onSuccess: invalidateQueries,
  })

  return (
    <div className="p-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Overview</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Live appliance state</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetchLive()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Safe Mode Active banner (driven by sysStatus for reliability) */}
      {sysStatus?.safe_mode?.active && (
        <SafeModeBanner
          safeMode={sysStatus.safe_mode}
          onClear={() => clearSafeMode.mutate()}
          isPending={clearSafeMode.isPending}
        />
      )}

      {/* Diagnostic Canvas Card */}
      <div className="mb-6">
        <DiagnosticCanvas live={live} />
      </div>

      {/* Player State Card */}
      <PlayerStateCard
        live={live}
        onEngageSafeMode={(reason) => engageSafeMode.mutate(reason)}
        onClearSafeMode={() => clearSafeMode.mutate()}
        engagePending={engageSafeMode.isPending}
        clearPending={clearSafeMode.isPending}
      />

      {/* Service health grid */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
          Service Health
        </p>
        <ServiceHealthGrid sysStatus={sysStatus} />
      </div>
    </div>
  )
}
