import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Filter } from 'lucide-react'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const ENTITY_FILTERS = [
  { value: 'all', label: 'All types' },
  { value: 'manifest', label: 'Manifest' },
  { value: 'campaign', label: 'Campaign' },
  { value: 'asset', label: 'Asset' },
  { value: 'system', label: 'System' },
]

const EVENT_COLORS: Record<string, string> = {
  'manifest.created':         'draft',
  'manifest.approved':        'approved',
  'manifest.rejected':        'rejected',
  'manifest.enabled':         'enabled',
  'manifest.disabled':        'disabled',
  'manifest.archived':        'archived',
  'campaign.created':         'draft',
  'campaign.updated':         'approved',
  'campaign.archived':        'archived',
  'campaign.manifest_added':  'approved',
  'campaign.manifest_removed':'disabled',
  'asset.uploaded':           'approved',
  'asset.archived':           'archived',
  'safe_mode.engaged':        'rejected',
  'safe_mode.cleared':        'enabled',
}

export function EventsPage() {
  const [entityFilter, setEntityFilter] = useState('all')
  const [page, setPage] = useState(1)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['events', entityFilter, page],
    queryFn: () => api.events.list({
      entity_type: entityFilter === 'all' ? undefined : entityFilter,
      page,
    }),
  })

  const pagination = data?.pagination

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">Audit Log</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Append-only record of all operator actions</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <Select value={entityFilter} onValueChange={v => { setEntityFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[160px] h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ENTITY_FILTERS.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
          </SelectContent>
        </Select>
        {pagination && (
          <span className="text-xs text-muted-foreground">{pagination.total} event{pagination.total !== 1 ? 's' : ''}</span>
        )}
      </div>

      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Timestamp</TableHead>
              <TableHead className="w-[200px]">Event</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-12 text-muted-foreground text-sm">Loading…</TableCell>
              </TableRow>
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-12 text-muted-foreground text-sm">No events found.</TableCell>
              </TableRow>
            )}
            {data?.items.map(ev => (
              <TableRow key={ev.id}>
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{formatDate(ev.created_at)}</TableCell>
                <TableCell>
                  <Badge variant={EVENT_COLORS[ev.event_type] ?? 'draft'} className="font-mono text-[10px]">
                    {ev.event_type}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span className="text-xs font-medium text-muted-foreground uppercase mr-2">{ev.entity_type}</span>
                  <span className="text-xs font-mono">{ev.entity_id}</span>
                </TableCell>
                <TableCell className="text-sm">{ev.actor}</TableCell>
                <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                  {ev.payload ? JSON.stringify(ev.payload) : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {pagination && pagination.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-xs text-muted-foreground">Page {page} of {pagination.pages}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= pagination.pages} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
