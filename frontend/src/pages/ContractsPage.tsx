import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { ExpiryBadge, PersonTypeBadge } from '../components/ui/Badge'
import { getExpiryReport } from '../api/contracts'
import { renewContract } from '../api/contracts'

const LEVELS = [
  { key: 'expired',  label: 'Expired',           colour: 'text-red-700 bg-red-50' },
  { key: 'critical', label: 'Critical (≤14 days)',colour: 'text-red-600 bg-red-50' },
  { key: 'warning',  label: 'Warning (≤30 days)', colour: 'text-orange-600 bg-orange-50' },
  { key: 'notice',   label: 'Notice (≤90 days)',  colour: 'text-blue-600 bg-blue-50' },
]

export function ContractsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  type ExpiryItem = { person_id: string; full_name: string; employee_id: string; person_type: string; days_remaining: number; contract_end: string; warning_level: string }
  const { data: reportData, isLoading } = useQuery({ queryKey: ['expiry-report'], queryFn: getExpiryReport })
  const report: Record<string, ExpiryItem[]> = reportData?.groups ?? {}

  const renewMutation = useMutation({
    mutationFn: (personId: string) => renewContract(personId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['expiry-report'] }),
  })

  if (isLoading) return <div className="flex items-center justify-center py-20 text-gray-400">Loading…</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Contract Management</h1>

      {LEVELS.map(({ key, label, colour }) => {
        const items: Array<{person_id: string; full_name: string; employee_id: string; person_type: string; days_remaining: number; contract_end: string; warning_level: string}> = report[key] ?? []
        if (items.length === 0) return null
        return (
          <Card key={key} padding={false}>
            <div className={`px-6 py-3 border-b border-gray-100 dark:border-gray-800 rounded-t-xl ${colour}`}>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <span className="font-semibold">{label}</span>
                <span className="ml-auto text-sm font-normal">{items.length} person{items.length !== 1 ? 's' : ''}</span>
              </div>
            </div>
            <div className="divide-y divide-gray-50">
              {items.map(item => (
                <div key={item.person_id} className="flex items-center gap-3 px-6 py-3">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => navigate(`/people/${item.person_id}`)}>
                    <p className="font-medium text-gray-900 dark:text-gray-100 hover:text-blue-700">{item.full_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{item.employee_id}</span>
                      <PersonTypeBadge type={item.person_type as 'employee' | 'contractor'} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpiryBadge level={item.warning_level} />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {key === 'expired' ? 'Expired' : `${item.days_remaining}d`}
                      {' · '}{new Date(item.contract_end).toLocaleDateString('en-GB')}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={renewMutation.isPending}
                    onClick={() => renewMutation.mutate(item.person_id)}
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Renew
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        )
      })}

      {LEVELS.every(({ key }) => !(report[key]?.length)) && (
        <Card>
          <div className="text-center py-8">
            <p className="text-lg font-medium text-green-600">All contracts are in good standing ✓</p>
            <p className="text-sm text-gray-400 mt-1">No contracts expiring within 90 days.</p>
          </div>
        </Card>
      )}
    </div>
  )
}
