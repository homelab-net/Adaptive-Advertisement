import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw, Filter } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import type { ManifestSummary, ManifestStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'

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

function ActionButtons({ manifest, onAction }: { manifest: ManifestSummary; onAction: (action: string, m: ManifestSummary) => void }) {
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
        <Button size="sm" variant="ghost" className="text-muted-foreground hover:text-destructive" onClick={() => onAction('archive', manifest)}>
          Archive
        </Button>
      )}
    </div>
  )
}

export function ManifestsPage() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(1)

  // Dialogs
  const [rejectTarget, setRejectTarget] = useState<ManifestSummary | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [archiveTarget, setArchiveTarget] = useState<ManifestSummary | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [newId, setNewId] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newJson, setNewJson] = useState('{\n  "items": []\n}')
  const [jsonError, setJsonError] = useState('')

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
      return api.manifests.create({ manifest_id: newId, title: newTitle, schema_version: '1.0.0', manifest_json: parsed })
    },
    onSuccess: () => { invalidate(); setCreateOpen(false); setNewId(''); setNewTitle(''); setNewJson('{\n  "items": []\n}') },
    onError: (e: Error) => setJsonError(e.message),
  })

  function handleAction(action: string, m: ManifestSummary) {
    if (action === 'approve')  approve.mutate(m)
    if (action === 'enable')   enable.mutate(m)
    if (action === 'disable')  disable.mutate(m)
    if (action === 'reject')   { setRejectTarget(m); setRejectReason('') }
    if (action === 'archive')  setArchiveTarget(m)
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
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add Content
          </Button>
        </div>
      </div>

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
              <TableHead className="w-[120px]">Status</TableHead>
              <TableHead>ID</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Approved</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead>Created</TableHead>
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
                <TableCell className="text-sm text-muted-foreground">{formatDate(m.approved_at)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDate(m.enabled_at)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDate(m.created_at)}</TableCell>
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

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Add Content</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
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
              <Textarea id="new-json" rows={8} className="font-mono text-xs" value={newJson} onChange={e => { setNewJson(e.target.value); setJsonError('') }} />
              {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
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
