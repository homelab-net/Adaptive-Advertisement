import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Megaphone, CalendarDays } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

const STATUS_COLORS: Record<string, string> = {
  draft: 'draft', active: 'active', paused: 'paused', archived: 'archived',
}

export function CampaignsPage() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => api.campaigns.list(),
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['campaigns'] })

  const create = useMutation({
    mutationFn: () => api.campaigns.create({ name, description: desc || undefined }),
    onSuccess: () => { invalidate(); setCreateOpen(false); setName(''); setDesc('') },
  })

  const archive = useMutation({
    mutationFn: (id: string) => api.campaigns.archive(id),
    onSuccess: invalidate,
  })

  const activate = useMutation({
    mutationFn: (id: string) => api.campaigns.update(id, { status: 'active' }),
    onSuccess: invalidate,
  })

  const pause = useMutation({
    mutationFn: (id: string) => api.campaigns.update(id, { status: 'paused' }),
    onSuccess: invalidate,
  })

  const campaigns = data?.items ?? []

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Campaigns</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Group approved content into scheduled campaigns</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Campaign
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      )}

      {!isLoading && campaigns.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-20 text-center">
          <Megaphone className="h-10 w-10 text-muted-foreground mb-3" />
          <p className="text-sm font-medium">No campaigns yet</p>
          <p className="text-xs text-muted-foreground mt-1">Create a campaign to group approved content for playback</p>
          <Button size="sm" className="mt-4" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            New Campaign
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {campaigns.map(c => (
          <Card key={c.id} className="flex flex-col">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-sm font-semibold leading-snug">{c.name}</CardTitle>
                <Badge variant={STATUS_COLORS[c.status]}>{c.status}</Badge>
              </div>
              {(c.start_at || c.end_at) && (
                <CardDescription className="flex items-center gap-1 text-xs mt-1">
                  <CalendarDays className="h-3 w-3" />
                  {c.start_at ? formatDate(c.start_at) : 'Now'}
                  {' → '}
                  {c.end_at ? formatDate(c.end_at) : 'Ongoing'}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="pt-0 flex-1 flex flex-col justify-end">
              <p className="text-xs text-muted-foreground mb-3">Created {formatDate(c.created_at)}</p>
              <div className="flex items-center gap-1.5 flex-wrap">
                {c.status === 'draft' && (
                  <Button size="sm" variant="outline-success" onClick={() => activate.mutate(c.id)}>Activate</Button>
                )}
                {c.status === 'active' && (
                  <Button size="sm" variant="outline" onClick={() => pause.mutate(c.id)}>Pause</Button>
                )}
                {c.status === 'paused' && (
                  <Button size="sm" variant="outline-success" onClick={() => activate.mutate(c.id)}>Resume</Button>
                )}
                {c.status !== 'archived' && (
                  <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-destructive" onClick={() => archive.mutate(c.id)}>Archive</Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Campaign</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input placeholder="Summer 2026 Promo" value={name} onChange={e => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Description (optional)</Label>
              <Textarea rows={2} placeholder="Brief description…" value={desc} onChange={e => setDesc(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
