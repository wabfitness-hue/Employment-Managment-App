import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PersonTypeBadge, StatusBadge, ExpiryBadge } from '../components/ui/Badge'
import { AuthImg } from '../components/ui/AuthImg'
import { listPeople, getPhotoUrl } from '../api/people'
import type { PersonFilter, PersonType, PersonStatus } from '../types'

export function PeopleListPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<PersonFilter>({})
  const [search, setSearch] = useState('')

  const { data: people = [], isLoading } = useQuery({
    queryKey: ['people', filter, search],
    queryFn: () => listPeople({ ...filter, search: search || undefined }),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">People</h1>
          <p className="text-sm text-gray-500 mt-0.5">{people.length} record{people.length !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => navigate('/people/new')}>
          <Plus className="h-4 w-4" /> Add person
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-48">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Search name, email, ID…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
          <select
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={filter.person_type ?? ''}
            onChange={e => setFilter(f => ({ ...f, person_type: (e.target.value as PersonType) || undefined }))}
          >
            <option value="">All types</option>
            <option value="employee">Employee</option>
            <option value="contractor">Contractor</option>
          </select>
          <select
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={filter.status ?? ''}
            onChange={e => setFilter(f => ({ ...f, status: (e.target.value as PersonStatus) || undefined }))}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
            <option value="terminated">Terminated</option>
          </select>
          <select
            className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={filter.expiry_warning ?? ''}
            onChange={e => setFilter(f => ({ ...f, expiry_warning: e.target.value || undefined }))}
          >
            <option value="">All contracts</option>
            <option value="critical">Critical (≤14d)</option>
            <option value="warning">Warning (≤30d)</option>
            <option value="notice">Notice (≤90d)</option>
            <option value="expired">Expired</option>
          </select>
        </div>
      </Card>

      {/* Table */}
      <Card padding={false}>
        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-gray-400">Loading…</div>
        ) : people.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <p className="text-gray-500">No people found.</p>
            <Button variant="secondary" onClick={() => { setFilter({}); setSearch('') }}>Clear filters</Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Name</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">ID</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Type</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Role / Dept</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Contract</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {people.map(p => (
                  <tr
                    key={p.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => navigate(`/people/${p.id}`)}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full overflow-hidden bg-gray-200 shrink-0">
                          {p.has_photo ? (
                            <AuthImg src={getPhotoUrl(p.id)} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <div className={`w-full h-full flex items-center justify-center text-xs font-bold ${p.person_type === 'employee' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700'}`}>
                              {p.full_name[0]}
                            </div>
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{p.full_name}</p>
                          <p className="text-xs text-gray-500">{p.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">{p.employee_id}</td>
                    <td className="px-4 py-3"><PersonTypeBadge type={p.person_type} /></td>
                    <td className="px-4 py-3">
                      <p className="text-gray-900">{p.job_title}</p>
                      <p className="text-xs text-gray-500">{p.department}{p.company_name ? ` · ${p.company_name}` : ''}</p>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                    <td className="px-4 py-3">
                      {p.contract_end && (
                        <div>
                          <ExpiryBadge level={p.expiry_warning} />
                          <p className="text-xs text-gray-500 mt-0.5">{new Date(p.contract_end).toLocaleDateString('en-GB')}</p>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Button variant="ghost" size="sm" onClick={e => { e.stopPropagation(); navigate(`/people/${p.id}`) }}>
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
