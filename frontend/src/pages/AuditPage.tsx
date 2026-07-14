import { useState } from 'react'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { Search, ChevronLeft, ChevronRight, Trash2, AlertTriangle } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { listAudit, listAuditActions, deleteAuditEntry, purgeAuditEntries } from '../api/audit'
import { useAuthStore } from '../store/auth'

const PAGE_SIZE = 50

function label(action: string) {
  return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function AuditPage() {
  const { user } = useAuthStore()
  const isSuperAdmin = user?.role === 'super_admin'
  const qc = useQueryClient()

  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [purgeModal, setPurgeModal] = useState(false)
  const [purgeDays, setPurgeDays] = useState('365')
  const [purgeConfirm, setPurgeConfirm] = useState('')
  const [purgeResult, setPurgeResult] = useState<string | null>(null)

  const { data: actionsData } = useQuery({ queryKey: ['audit-actions'], queryFn: listAuditActions })
  const { data, isLoading } = useQuery({
    queryKey: ['audit', offset, action, q],
    queryFn: () => listAudit({ limit: PAGE_SIZE, offset, action: action || undefined, q: q || undefined }),
    placeholderData: keepPreviousData,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAuditEntry(id),
    onSuccess: () => {
      setDeleteTarget(null)
      qc.invalidateQueries({ queryKey: ['audit'] })
      qc.invalidateQueries({ queryKey: ['audit-actions'] })
    },
  })

  const purgeMutation = useMutation({
    mutationFn: () => purgeAuditEntries(Number(purgeDays)),
    onSuccess: (res) => {
      setPurgeResult(`Deleted ${res.deleted} entr${res.deleted === 1 ? 'y' : 'ies'}.`)
      setPurgeConfirm('')
      qc.invalidateQueries({ queryKey: ['audit'] })
      qc.invalidateQueries({ queryKey: ['audit-actions'] })
    },
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE_SIZE, total)

  function applySearch() { setOffset(0); setQ(qInput.trim()) }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Audit log</h1>
        {isSuperAdmin && (
          <Button size="sm" variant="secondary" onClick={() => { setPurgeModal(true); setPurgeResult(null) }}>
            <Trash2 className="h-4 w-4" /> Clear old entries
          </Button>
        )}
      </div>

      <Card>
        <CardHeader
          title="Activity"
          subtitle={isSuperAdmin ? 'Deletions are themselves logged, so a removal is never silent' : 'Every recorded action — read-only'}
        />

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-4">
          <select
            value={action}
            onChange={e => { setOffset(0); setAction(e.target.value) }}
            className="px-3 py-2 rounded-lg border text-sm border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
          >
            <option value="">All actions</option>
            {actionsData?.actions.map(a => <option key={a} value={a}>{label(a)}</option>)}
          </select>
          <div className="flex gap-2 flex-1 min-w-[200px]">
            <input
              value={qInput}
              onChange={e => setQInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') applySearch() }}
              placeholder="Search action, IP, or user…"
              className="flex-1 px-3 py-2 rounded-lg border text-sm border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
            />
            <Button size="sm" variant="secondary" onClick={applySearch}><Search className="h-4 w-4" /> Search</Button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-4 font-medium">Time</th>
                <th className="py-2 pr-4 font-medium">User</th>
                <th className="py-2 pr-4 font-medium">Action</th>
                <th className="py-2 pr-4 font-medium">Target</th>
                <th className="py-2 pr-4 font-medium">IP</th>
                <th className="py-2 font-medium">Details</th>
                {isSuperAdmin && <th className="py-2 pl-2 font-medium" />}
              </tr>
            </thead>
            <tbody>
              {items.map(e => (
                <tr key={e.id} className="border-b border-gray-100 dark:border-gray-800 align-top">
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-600 dark:text-gray-300">
                    {e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-700 dark:text-gray-200">
                    {e.actor_email ?? <span className="text-gray-400">system</span>}
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap font-medium text-gray-900 dark:text-gray-100">{label(e.action)}</td>
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-500 dark:text-gray-400">
                    {e.target_type ? `${e.target_type}${e.target_id ? ` ${e.target_id.slice(0, 8)}` : ''}` : '—'}
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap font-mono text-xs text-gray-500 dark:text-gray-400">{e.ip_address ?? '—'}</td>
                  <td className="py-2 font-mono text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate" title={JSON.stringify(e.detail)}>
                    {Object.keys(e.detail).length ? JSON.stringify(e.detail) : '—'}
                  </td>
                  {isSuperAdmin && (
                    <td className="py-2 pl-2 whitespace-nowrap">
                      <button onClick={() => setDeleteTarget(e.id)} className="text-red-500 hover:text-red-700 p-1" title="Delete this entry">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={isSuperAdmin ? 7 : 6} className="py-8 text-center text-gray-400">No audit entries found.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 text-sm text-gray-500 dark:text-gray-400">
          <span>{from}–{to} of {total}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              <ChevronLeft className="h-4 w-4" /> Prev
            </Button>
            <Button size="sm" variant="secondary" disabled={to >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Single-entry delete confirmation */}
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete audit entry" size="sm">
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            This entry will be permanently removed. The deletion itself will be recorded as a new audit entry.
          </p>
          <div className="flex gap-3">
            <Button
              variant="danger"
              className="flex-1"
              loading={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
            >
              Delete permanently
            </Button>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>Cancel</Button>
          </div>
        </div>
      </Modal>

      {/* Bulk purge confirmation */}
      <Modal open={purgeModal} onClose={() => { setPurgeModal(false); setPurgeConfirm('') }} title="Clear old audit entries">
        <div className="space-y-4">
          <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800 dark:text-amber-300">
              This permanently deletes every entry older than the chosen age. It cannot be undone — the purge itself will be logged.
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Delete entries older than (days)</label>
            <input
              type="number"
              min={1}
              value={purgeDays}
              onChange={e => setPurgeDays(e.target.value)}
              className="w-32 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Type DELETE to confirm</label>
            <input
              value={purgeConfirm}
              onChange={e => setPurgeConfirm(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 text-sm font-mono"
            />
          </div>
          {purgeResult && <p className="text-sm text-green-600">{purgeResult}</p>}
          <div className="flex gap-3">
            <Button
              variant="danger"
              className="flex-1"
              loading={purgeMutation.isPending}
              disabled={purgeConfirm !== 'DELETE' || !purgeDays || Number(purgeDays) < 1}
              onClick={() => purgeMutation.mutate()}
            >
              Clear entries
            </Button>
            <Button variant="secondary" onClick={() => { setPurgeModal(false); setPurgeConfirm('') }}>Close</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
