import { useQuery } from '@tanstack/react-query'
import { Shield, MapPin } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import api from '../api/client'

export function AccessPage() {
  const { data: zones = [] } = useQuery({ queryKey: ['zones'], queryFn: () => api.get('/access/zones').then(r => r.data) })
  const { data: profiles = [] } = useQuery({ queryKey: ['profiles'], queryFn: () => api.get('/access/profiles').then(r => r.data) })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Access Control</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader title="Access Zones" subtitle="Physical locations controlled by access system" />
          <div className="space-y-2">
            {zones.map((z: { id: string; code: string; name: string; floor?: string }) => (
              <div key={z.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <MapPin className="h-4 w-4 text-gray-400 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{z.name}</p>
                  {z.floor && <p className="text-xs text-gray-500">Floor: {z.floor}</p>}
                </div>
                <Badge variant="gray">{z.code}</Badge>
              </div>
            ))}
            {zones.length === 0 && <p className="text-sm text-gray-400 py-4 text-center">No zones configured.</p>}
          </div>
        </Card>

        <Card>
          <CardHeader title="Access Profiles" subtitle="Predefined zone bundles assigned to people" />
          <div className="space-y-2">
            {profiles.map((p: { id: string; name: string; description?: string }) => (
              <div key={p.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <Shield className="h-4 w-4 text-blue-500 shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{p.name}</p>
                  {p.description && <p className="text-xs text-gray-500">{p.description}</p>}
                </div>
              </div>
            ))}
            {profiles.length === 0 && <p className="text-sm text-gray-400 py-4 text-center">No profiles configured.</p>}
          </div>
        </Card>
      </div>
    </div>
  )
}
