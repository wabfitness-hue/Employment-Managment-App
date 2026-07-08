import { useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { listAudit, listAuditActions } from '../api/audit'

const PAGE_SIZE = 50

function label(action: string) {
  return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function AuditPage() {
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [qInput, setQInput] = useState('')
  const [q, setQ] = useState('')

  const { data: actionsData } = useQuery({ queryKey: ['audit-actions'], queryFn: listAuditActions })
  const { data, isLoading } = useQuery({
    queryKey: ['audit', offset, action, q],
    queryFn: () => listAudit({ limit: PAGE_SIZE, offset, action: action || undefined, q: q || undefined }),
    placeholderData: keepPreviousData,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE_SIZE, total)

  function applySearch() { setOffset(0); setQ(qInput.trim()) }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Audit log</h1>

      <Card>
        <CardHeader title="Activity" subtitle="Every recorded action — read-only" />

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
                </tr>
              ))}
              {!isLoading && items.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-gray-400">No audit entries found.</td></tr>
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
    </div>
  )
}
