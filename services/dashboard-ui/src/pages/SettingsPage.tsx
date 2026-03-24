import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'

export function SettingsPage() {
  const qc = useQueryClient()
  const [engageOpen, setEngageOpen] = useState(false)
  const [reason, setReason] = useState('')

  const { data: safeMode } = useQuery({
    queryKey: ['safe-mode'],
    queryFn: api.system.safeMode,
    refetchInterval: 15_000,
  })

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['safe-mode'] })
    qc.invalidateQueries({ queryKey: ['system-status'] })
  }

  const engage = useMutation({
    mutationFn: () => api.system.engageSafeMode(reason),
    onSuccess: () => { invalidate(); setEngageOpen(false); setReason('') },
  })

  const clear = useMutation({
    mutationFn: api.system.clearSafeMode,
    onSuccess: invalidate,
  })

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Appliance controls and safe-mode management</p>
      </div>

      {/* Safe mode card */}
      <Card className={safeMode?.active ? 'border-amber-300' : ''}>
        <CardHeader>
          <div className="flex items-center gap-2">
            {safeMode?.active
              ? <ShieldAlert className="h-5 w-5 text-amber-600" />
              : <ShieldCheck className="h-5 w-5 text-emerald-600" />
            }
            <CardTitle className="text-base">Safe Mode</CardTitle>
          </div>
          <CardDescription>
            {safeMode?.active
              ? 'The appliance is in safe mode. Player will show the fallback bundle. Adaptive playback is suspended.'
              : 'Normal operation. The player is serving approved adaptive content.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {safeMode?.active && (
            <div className="rounded-md bg-amber-50 border border-amber-200 p-3 space-y-1 text-sm">
              {safeMode.reason && <p><span className="font-medium">Reason:</span> {safeMode.reason}</p>}
              {safeMode.activated_at && <p><span className="font-medium">Since:</span> {formatDate(safeMode.activated_at)}</p>}
            </div>
          )}
          <div className="flex gap-2">
            {!safeMode?.active && (
              <Button variant="outline-destructive" onClick={() => setEngageOpen(true)}>
                <ShieldAlert className="h-4 w-4" />
                Engage Safe Mode
              </Button>
            )}
            {safeMode?.active && (
              <Button variant="outline-success" disabled={clear.isPending} onClick={() => clear.mutate()}>
                <ShieldCheck className="h-4 w-4" />
                Clear Safe Mode
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Safe-mode intent is stored in the database. The supervisor service relays it to the player (ICD-8).
            Playback continuity is preserved during the transition.
          </p>
        </CardContent>
      </Card>

      {/* Engage confirm dialog */}
      <AlertDialog open={engageOpen} onOpenChange={setEngageOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-600" />
              Engage Safe Mode?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The player will switch to the fallback bundle and stop adaptive playback until safe mode is cleared.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-1.5 px-1">
            <Label htmlFor="sm-reason">Reason</Label>
            <Textarea
              id="sm-reason"
              rows={2}
              placeholder="e.g. Maintenance window, Content review…"
              value={reason}
              onChange={e => setReason(e.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-amber-600 hover:bg-amber-700 text-white"
              onClick={() => engage.mutate()}
              disabled={!reason.trim() || engage.isPending}
            >
              Engage Safe Mode
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
