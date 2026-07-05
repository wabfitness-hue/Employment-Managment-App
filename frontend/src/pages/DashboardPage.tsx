import { useQuery } from '@tanstack/react-query'
import { Users, AlertTriangle } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Badge, ExpiryBadge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { listPeople } from '../api/people'
import { getExpiryReport } from '../api/contracts'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

function StatCard({ label, value, icon: Icon, colour }: { label: string; value: number | string; icon: React.ElementType; colour: string }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${colour}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </Card>
  )
}

export function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const { data: people = [] } = useQuery({ queryKey: ['people'], queryFn: () => listPeople({ limit: 200 }) })
  const { data: expiryReport } = useQuery({ queryKey: ['expiry-report'], queryFn: getExpiryReport })

  const active = people.filter(p => p.status === 'active').length
  const employees = people.filter(p => p.person_type === 'employee').length
  const contractors = people.filter(p => p.person_type === 'contractor').length
  const expiring = (expiryReport?.critical?.length ?? 0) + (expiryReport?.warning?.length ?? 0)

  const recentPeople = people.slice(0, 5)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Good {new Date().getHours() < 12 ? 'morning' : 'afternoon'}, {user?.display_name?.split(' ')[0]}
        </h1>
        <p className="text-gray-500 text-sm mt-1">{new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Active People" value={active} icon={Users} colour="bg-blue-600" />
        <StatCard label="Employees" value={employees} icon={Users} colour="bg-indigo-600" />
        <StatCard label="Contractors" value={contractors} icon={Users} colour="bg-orange-500" />
        <StatCard label="Expiring Soon" value={expiring} icon={AlertTriangle} colour={expiring > 0 ? 'bg-red-500' : 'bg-green-500'} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent people */}
        <Card padding={false}>
          <div className="p-6 border-b border-gray-100">
            <CardHeader
              title="Recent People"
              action={<Button variant="ghost" size="sm" onClick={() => navigate('/people')}>View all</Button>}
            />
          </div>
          <div className="divide-y divide-gray-50">
            {recentPeople.map(p => (
              <div
                key={p.id}
                className="flex items-center gap-3 px-6 py-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => navigate(`/people/${p.id}`)}
              >
                <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-sm font-bold shrink-0">
                  {p.full_name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{p.full_name}</p>
                  <p className="text-xs text-gray-500 truncate">{p.job_title} · {p.employee_id}</p>
                </div>
                <Badge variant={p.person_type === 'employee' ? 'blue' : 'orange'}>
                  {p.person_type === 'employee' ? 'EMP' : 'CTR'}
                </Badge>
              </div>
            ))}
            {recentPeople.length === 0 && (
              <p className="text-sm text-gray-400 px-6 py-8 text-center">No people yet. <button className="text-blue-600 hover:underline" onClick={() => navigate('/people/new')}>Add the first person</button></p>
            )}
          </div>
        </Card>

        {/* Expiry alerts */}
        <Card padding={false}>
          <div className="p-6 border-b border-gray-100">
            <CardHeader
              title="Contract Alerts"
              action={<Button variant="ghost" size="sm" onClick={() => navigate('/contracts')}>View all</Button>}
            />
          </div>
          <div className="divide-y divide-gray-50">
            {[...(expiryReport?.groups?.critical ?? []), ...(expiryReport?.groups?.warning ?? [])].slice(0, 5).map((item: {person_id: string; full_name: string; employee_id: string; days_remaining: number; warning_level: string}) => (
              <div
                key={item.person_id}
                className="flex items-center gap-3 px-6 py-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => navigate(`/people/${item.person_id}`)}
              >
                <AlertTriangle className="h-4 w-4 text-orange-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.full_name}</p>
                  <p className="text-xs text-gray-500">{item.employee_id} · {item.days_remaining}d remaining</p>
                </div>
                <ExpiryBadge level={item.warning_level} />
              </div>
            ))}
            {expiring === 0 && (
              <p className="text-sm text-gray-400 px-6 py-8 text-center">No urgent contract alerts.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
