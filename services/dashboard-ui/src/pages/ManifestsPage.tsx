import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Filter, Tags, RotateCcw } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { ManifestSummary, ManifestStatus, AudienceTag } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Tag taxonomy — must stay in sync with rule_generator.ALL_VALID_TAGS
// ---------------------------------------------------------------------------

type TagGroup = {
  label: string
  description: string
  tags: { key: AudienceTag; label: string }[]
  radioGroup?: boolean  // true = mutually exclusive (radio), false = multi-select
}

const TAG_GROUPS: TagGroup[] = [
  {
    label: 'Who is this ad for?',
    description: 'Select the audience this content is designed to reach.',
    tags: [
      { key: 'attract',          label: 'Attract loop (no audience)' },
      { key: 'general',          label: 'General audience' },
      { key: 'solo_adult',       label: 'Solo adult' },
      { key: 'group_adults',     label: 'Group of adults' },
      { key: 'adult_with_child', label: 'Adults with children' },
      { key: 'teenager_group',   label: 'Teenagers' },
      { key: 'seniors',          label: 'Seniors' },
    ],
  },
  {
    label: 'When should it run?',
    description: 'Choose the time windows when this content is most relevant. Leave blank for no time restriction.',
    tags: [
      { key: 'time_morning',    label: 'Morning (6 AM – 11 AM)' },
      { key: 'time_lunch',      label: 'Lunch (11 AM – 2 PM)' },
      { key: 'time_afternoon',  label: 'Afternoon (2 PM – 5 PM)' },
      { key: 'time_happy_hour', label: 'Happy Hour (4 PM – 6 PM)' },
      { key: 'time_evening',    label: 'Evening (6 PM – 10 PM)' },
      { key: 'time_late_night', label: 'Late Night (10 PM – 6 AM)' },
      { key: 'time_all_day',    label: 'All day' },
    ],
  },
  {
    label: 'What type of content is this?',
    description: 'Tag promotional or seasonal content to give it higher priority during its time window.',
    tags: [
      { key: 'promo_featured',     label: 'Featured promotion' },
      { key: 'promo_limited_time', label: 'Limited-time offer' },
      { key: 'promo_seasonal',     label: 'Seasonal content' },
    ],
  },
  {
    label: 'How often should it appear?',
    description: 'Control whether this ad shows only during its time window, or also appears occasionally throughout the day.',
    radioGroup: true,
    tags: [
      { key: 'freq_primary',   label: 'During its time window only' },
      { key: 'freq_recurring', label: 'During its time, plus occasionally all day' },
      { key: 'freq_ambient',   label: 'Throughout the day as background filler' },
    ],
  },
]

const ALL_TAG_LABELS: Record<AudienceTag, string> = Object.fromEntries(
  TAG_GROUPS.flatMap(g => g.tags.map(t => [t.key, t.label]))
) as Record<AudienceTag, string>

const FREQ_KEYS: AudienceTag[] = ['freq_primary', 'freq_recurring', 'freq_ambient']

// Tag chip colour classes by category
function tagChipClass(tag: AudienceTag): string {
  if (tag.startsWith('time_'))  return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300'
  if (tag.startsWith('promo_')) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
  if (tag.startsWith('freq_'))  return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
  return 'bg-muted text-muted-foreground'
}

function AudienceTagChip({ tag }: { tag: AudienceTag }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', tagChipClass(tag))}>
      {ALL_TAG_LABELS[tag] ?? tag}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Tag selector component (reused in create + edit dialogs)
// ---------------------------------------------------------------------------

function TagSelector({
  selected,
  onChange,
}: {
  selected: AudienceTag[]
  onChange: (tags: AudienceTag[]) => void
}) {
  function toggle(key: AudienceTag, radioGroup?: boolean) {
    if (radioGroup) {
      // For frequency group: if already selected, deselect; otherwise replace all freq keys
      if (selected.includes(key)) {
        onChange(selected.filter(t => t !== key))
      } else {
        onChange([...selected.filter(t => !FREQ_KEYS.includes(t)), key])
      }
    } else {
      if (selected.includes(key)) {
        onChange(selected.filter(t => t !== key))
      } else {
        onChange([...selected, key])
      }
    }
  }

  // Plain-English summary of what will happen
  const audienceTags = selected.filter(t => !t.startsWith('time_') && !t.startsWith('promo_') && !t.startsWith('freq_'))
  const timeTags = selected.filter(t => t.startsWith('time_'))
  const promoTags = selected.filter(t => t.startsWith('promo_'))
  const freqTag = selected.find(t => t.startsWith('freq_'))

  const summaryParts: string[] = []
  if (audienceTags.length > 0) {
    summaryParts.push(`targeted at ${audienceTags.map(t => ALL_TAG_LABELS[t]?.toLowerCase()).join(', ')}`)
  }
  if (timeTags.length > 0) {
    summaryParts.push(`during ${timeTags.map(t => ALL_TAG_LABELS[t]).join(' and ')}`)
  }
  if (promoTags.length > 0) {
    summaryParts.push(`marked as ${promoTags.map(t => ALL_TAG_LABELS[t]?.toLowerCase()).join(', ')}`)
  }
  if (freqTag === 'freq_recurring') summaryParts.push('appearing occasionally throughout the rest of the day')
  if (freqTag === 'freq_ambient')   summaryParts.push('filling background slots all day')

  const summary = summaryParts.length > 0
    ? `This ad will play ${summaryParts.join(', ')}.`
    : null

  return (
    <div className="space-y-5">
      {TAG_GROUPS.map(group => (
        <div key={group.label} className="space-y-2">
          <div>
            <p className="text-sm font-medium text-foreground">{group.label}</p>
            <p className="text-xs text-muted-foreground">{group.description}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {group.tags.map(({ key, label }) => {
              const active = selected.includes(key)
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggle(key, group.radioGroup)}
                  className={cn(
                    'rounded-full px-3 py-1 text-sm font-medium border transition-colors select-none',
                    active
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-muted text-muted-foreground border-border hover:border-primary/50 hover:text-foreground'
                  )}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>
      ))}

      {/* Plain-English preview */}
      {summary ? (
        <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
          {summary}
        </div>
      ) : (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          No tags selected — this content will not generate any automatic display rules.
          You can still assign it to rules manually.
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'enabled', label: 'Enabled' },
  { value: 'disabled', label: 'Disabled' },
  { value: 'rejected', label: 'Rejected' },
]

function StatusBadge({ status }: { status: ManifestStatus }) {
  const labels: Record<ManifestStatus, string> = {
    draft: 'Draft', approved: 'Approved', rejected: 'Rejected',
    enabled: 'Live', disabled: 'Disabled', archived: 'Archived',
  }
  return <Badge variant={status}>{labels[status]}</Badge>
}

function ActionButtons({
  manifest,
  onAction,
}: {
  manifest: ManifestSummary
  onAction: (action: string, m: ManifestSummary) => void
}) {
  const { status } = manifest
  return (
    <div className="flex items-center gap-1.5">
      {(status === 'draft' || status === 'rejected') && (
        <Button size="sm" variant="outline-success" onClick={() => onAction('approve', manifest)}>
          Approve
        </Button>
      )}
      {(status === 'draft' || status === 'approved') && (
        <Button size="sm" variant="outline-destructive" onClick={() => onAction('reject', manifest)}>
          Reject
        </Button>
      )}
      {(status === 'approved' || status === 'disabled') && (
        <Button size="sm" variant="default" onClick={() => onAction('enable', manifest)}>
          Enable
        </Button>
      )}
      {status === 'enabled' && (
        <Button size="sm" variant="outline" onClick={() => onAction('disable', manifest)}>
          Disable
        </Button>
      )}
      {status !== 'archived' && (
        <Button
          size="sm"
          variant="ghost"
          title="Edit audience tags"
          onClick={() => onAction('editTags', manifest)}
        >
          <Tags className="h-3.5 w-3.5" />
        </Button>
      )}
      {status !== 'archived' && (
        <Button
          size="sm"
          variant="ghost"
          className="text-muted-foreground hover:text-destructive"
          onClick={() => onAction('archive', manifest)}
        >
          Archive
        </Button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function ManifestsPage() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)

  // Dialogs
  const [rejectTarget, setRejectTarget] = useState<ManifestSummary | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [archiveTarget, setArchiveTarget] = useState<ManifestSummary | null>(null)

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false)
  const [newId, setNewId] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newJson, setNewJson] = useState('{\n  "items": []\n}')
  const [jsonError, setJsonError] = useState('')
  const [newTags, setNewTags] = useState<AudienceTag[]>([])

  // Edit-tags dialog
  const [editTagsTarget, setEditTagsTarget] = useState<ManifestSummary | null>(null)
  const [editTags, setEditTags] = useState<AudienceTag[]>([])

  // Sync-rules state
  const [syncResult, setSyncResult] = useState<string | null>(null)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['manifests', statusFilter, page],
    queryFn: () => api.manifests.list({ status: statusFilter === 'all' ? undefined : statusFilter, page }),
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['manifests'] })

  const approve  = useMutation({ mutationFn: (m: ManifestSummary) => api.manifests.approve(m.manifest_id),  onSuccess: invalidate })
  const enable   = useMutation({ mutationFn: (m: ManifestSummary) => api.manifests.enable(m.manifest_id),   onSuccess: invalidate })
  const disable  = useMutation({ mutationFn: (m: ManifestSummary) => api.manifests.disable(m.manifest_id),  onSuccess: invalidate })
  const archive  = useMutation({ mutationFn: (m: ManifestSummary) => api.manifests.archive(m.manifest_id),  onSuccess: invalidate })
  const reject   = useMutation({
    mutationFn: (m: ManifestSummary) => api.manifests.reject(m.manifest_id, rejectReason),
    onSuccess: () => { invalidate(); setRejectTarget(null); setRejectReason('') },
  })
  const create = useMutation({
    mutationFn: () => {
      let parsed: unknown
      try { parsed = JSON.parse(newJson) } catch { throw new Error('Invalid JSON') }
      return api.manifests.create({
        manifest_id: newId,
        title: newTitle,
        schema_version: '1.0.0',
        manifest_json: parsed,
        audience_tags: newTags,
      })
    },
    onSuccess: () => {
      invalidate()
      setCreateOpen(false)
      setNewId(''); setNewTitle(''); setNewJson('{\n  "items": []\n}'); setNewTags([])
    },
    onError: (e: Error) => setJsonError(e.message),
  })
  const updateTags = useMutation({
    mutationFn: () => api.manifests.updateTags(editTagsTarget!.manifest_id, editTags),
    onSuccess: () => { invalidate(); setEditTagsTarget(null) },
  })
  const syncRules = useMutation({
    mutationFn: () => api.manifests.syncRules(),
    onSuccess: (result) => {
      setSyncResult(
        `Rules synced — ${result.generated_rules} rules from ${result.enabled_manifests} enabled manifests.` +
        (result.optimizer_reloaded ? '' : ' (Warning: optimizer reload failed — rules file written to disk.)')
      )
    },
    onError: (e: Error) => setSyncResult(`Sync failed: ${e.message}`),
  })

  function handleAction(action: string, m: ManifestSummary) {
    if (action === 'approve')   approve.mutate(m)
    if (action === 'enable')    enable.mutate(m)
    if (action === 'disable')   disable.mutate(m)
    if (action === 'reject')    { setRejectTarget(m); setRejectReason('') }
    if (action === 'archive')   setArchiveTarget(m)
    if (action === 'editTags')  { setEditTagsTarget(m); setEditTags((m.audience_tags ?? []) as AudienceTag[]) }
  }

  const pagination = data?.pagination

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Content</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage and approve creative manifests for playback</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => syncRules.mutate()}
            disabled={syncRules.isPending}
            title="Rebuild decision rules from all enabled manifests' audience tags and apply them immediately"
          >
            <RotateCcw className={cn('h-3.5 w-3.5 mr-1', syncRules.isPending && 'animate-spin')} />
            {syncRules.isPending ? 'Syncing…' : 'Sync Rules'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add Content
          </Button>
        </div>
      </div>

      {/* Sync result banner */}
      {syncResult && (
        <div className={cn(
          'mb-4 rounded-md border px-3 py-2 text-sm flex items-center justify-between',
          syncResult.includes('failed') || syncResult.includes('Warning')
            ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
            : 'border-green-300 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-950/30 dark:text-green-300'
        )}>
          <span>{syncResult}</span>
          <button className="ml-4 text-xs underline opacity-70 hover:opacity-100" onClick={() => setSyncResult(null)}>Dismiss</button>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[160px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {pagination && (
          <span className="text-xs text-muted-foreground">{pagination.total} manifest{pagination.total !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead>ID</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Audience Tags</TableHead>
              <TableHead>Approved</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground text-sm">Loading…</TableCell>
              </TableRow>
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-12 text-muted-foreground text-sm">
                  No manifests found.{' '}
                  <button className="text-primary hover:underline" onClick={() => setCreateOpen(true)}>Add your first one.</button>
                </TableCell>
              </TableRow>
            )}
            {data?.items.map(m => (
              <TableRow key={m.id}>
                <TableCell><StatusBadge status={m.status} /></TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{m.manifest_id}</TableCell>
                <TableCell className="font-medium">{m.title}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {(m.audience_tags ?? []).length > 0
                      ? (m.audience_tags as AudienceTag[]).map(t => <AudienceTagChip key={t} tag={t} />)
                      : <span className="text-xs text-muted-foreground">—</span>
                    }
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDate(m.approved_at)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDate(m.enabled_at)}</TableCell>
                <TableCell className="text-right">
                  <ActionButtons manifest={m} onAction={handleAction} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {pagination && pagination.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-muted-foreground">Page {page} of {pagination.pages}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= pagination.pages} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </div>
      )}

      {/* Reject dialog */}
      <Dialog open={!!rejectTarget} onOpenChange={open => !open && setRejectTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Manifest</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">
              Rejecting <span className="font-medium text-foreground">{rejectTarget?.title}</span>. Provide a reason.
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="reject-reason">Reason</Label>
              <Textarea id="reject-reason" rows={3} value={rejectReason} onChange={e => setRejectReason(e.target.value)} placeholder="Describe what needs to be corrected…" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectTarget(null)}>Cancel</Button>
            <Button variant="destructive" disabled={!rejectReason.trim() || reject.isPending} onClick={() => rejectTarget && reject.mutate(rejectTarget)}>
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Archive confirm */}
      <AlertDialog open={!!archiveTarget} onOpenChange={open => !open && setArchiveTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive manifest?</AlertDialogTitle>
            <AlertDialogDescription>
              <span className="font-medium">{archiveTarget?.title}</span> will be archived. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setArchiveTarget(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => { archiveTarget && archive.mutate(archiveTarget); setArchiveTarget(null) }}
            >
              Archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit tags dialog */}
      <Dialog open={!!editTagsTarget} onOpenChange={open => !open && setEditTagsTarget(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Audience Tags — {editTagsTarget?.title}</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <TagSelector selected={editTags} onChange={setEditTags} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTagsTarget(null)}>Cancel</Button>
            <Button disabled={updateTags.isPending} onClick={() => updateTags.mutate()}>
              Save Tags
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Content</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 py-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="new-id">Manifest ID</Label>
                <Input id="new-id" placeholder="promo-summer-2026" value={newId} onChange={e => setNewId(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new-title">Title</Label>
                <Input id="new-title" placeholder="Summer Promo 2026" value={newTitle} onChange={e => setNewTitle(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new-json">Manifest JSON (ICD-5)</Label>
              <Textarea id="new-json" rows={5} className="font-mono text-xs" value={newJson} onChange={e => { setNewJson(e.target.value); setJsonError('') }} />
              {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
            </div>
            <div className="border-t pt-4">
              <TagSelector selected={newTags} onChange={setNewTags} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={!newId.trim() || !newTitle.trim() || create.isPending} onClick={() => create.mutate()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
