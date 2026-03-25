import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Megaphone, CalendarDays, Link2, X } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { CampaignDetail } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function CampaignsPage() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [linkTarget, setLinkTarget] = useState<CampaignDetail | null>(null)
  const [linkManifestId, setLinkManifestId] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => api.campaigns.list(),
  })

  // Manifests list for the link dialog
  const { data: manifestsData } = useQuery({
    queryKey: ['manifests', 'approved'],
    queryFn: () => api.manifests.list({ status: 'approved' }),
    enabled: !!linkTarget,
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

  const addManifest = useMutation({
    mutationFn: ({ campaignId, manifestId }: { campaignId: string; manifestId: string }) =>
      api.campaigns.addManifest(campaignId, manifestId),
    onSuccess: () => { invalidate(); setLinkManifestId('') },
  })

  const removeManifest = useMutation({
    mutationFn: ({ campaignId, manifestId }: { campaignId: string; manifestId: string }) =>
      api.campaigns.removeManifest(campaignId, manifestId),
    onSuccess: invalidate,
  })

  const campaigns = (data?.items ?? []) as CampaignDetail[]

  const availableManifests = (manifestsData?.items ?? []).filter(
    m => !(linkTarget?.manifest_ids ?? []).includes(m.manifest_id)
  )

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Campaigns</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Group approved manifests into scheduled campaigns for A/B comparison</p>
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
          <p className="text-xs text-muted-foreground mt-1">
            Create a campaign to group approved manifests for A/B testing and scheduled playback
          </p>
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
                <Badge variant={c.status}>{c.status}</Badge>
              </div>
              {c.description && (
                <CardDescription className="text-xs mt-1">{c.description}</CardDescription>
              )}
              {(c.start_at || c.end_at) && (
                <CardDescription className="flex items-center gap-1 text-xs mt-1">
                  <CalendarDays className="h-3 w-3" />
                  {c.start_at ? formatDate(c.start_at) : 'Now'}
                  {' → '}
                  {c.end_at ? formatDate(c.end_at) : 'Ongoing'}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="pt-0 flex-1 flex flex-col gap-3">
              {/* Linked manifests */}
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1.5">
                  Manifests ({c.manifest_ids?.length ?? 0})
                </p>
                {(c.manifest_ids?.length ?? 0) === 0 ? (
                  <p className="text-xs text-muted-foreground italic">No manifests linked</p>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {c.manifest_ids?.map(mid => (
                      <span
                        key={mid}
                        className="inline-flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-muted-foreground"
                      >
                        {mid}
                        <button
                          className="ml-0.5 hover:text-destructive"
                          onClick={() => removeManifest.mutate({ campaignId: c.id, manifestId: mid })}
                        >
                          <X className="h-2.5 w-2.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-1.5 flex-wrap mt-auto">
                {c.status === 'draft' && (
                  <Button size="sm" variant="outline-success" onClick={() => activate.mutate(c.id)}>Activate</Button>
                )}
                {c.status === 'active' && (
                  <Button size="sm" variant="outline" onClick={() => pause.mutate(c.id)}>Pause</Button>
                )}
                {c.status === 'paused' && (
                  <Button size="sm" variant="outline-success" onClick={() => activate.mutate(c.id)}>Resume</Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => { setLinkTarget(c); setLinkManifestId('') }}
                >
                  <Link2 className="h-3 w-3" />
                  Link Manifest
                </Button>
                {c.status !== 'archived' && (
                  <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-destructive" onClick={() => archive.mutate(c.id)}>
                    Archive
                  </Button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">Created {formatDate(c.created_at)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Create dialog */}
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

      {/* Link manifest dialog */}
      <Dialog open={!!linkTarget} onOpenChange={open => !open && setLinkTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Link Manifest to "{linkTarget?.name}"</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              Select an approved manifest to add to this campaign.
              Campaigns with multiple manifests enable A/B comparison in Analytics.
            </p>
            <div className="space-y-1.5">
              <Label>Approved Manifest</Label>
              <Select value={linkManifestId} onValueChange={setLinkManifestId}>
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder="Select manifest…" />
                </SelectTrigger>
                <SelectContent>
                  {availableManifests.map(m => (
                    <SelectItem key={m.manifest_id} value={m.manifest_id}>
                      {m.title} <span className="text-muted-foreground font-mono text-xs">({m.manifest_id})</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {availableManifests.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No additional approved manifests available. All approved manifests are already linked,
                or no manifests have been approved yet.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLinkTarget(null)}>Cancel</Button>
            <Button
              disabled={!linkManifestId || addManifest.isPending}
              onClick={() => {
                if (linkTarget && linkManifestId) {
                  addManifest.mutate({ campaignId: linkTarget.id, manifestId: linkManifestId })
                }
              }}
            >
              Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
