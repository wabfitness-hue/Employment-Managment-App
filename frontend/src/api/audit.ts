import api from './client'

export interface AuditEntry {
  id: string
  timestamp: string | null
  action: string
  actor_email: string | null
  actor_name: string | null
  target_type: string | null
  target_id: string | null
  ip_address: string | null
  detail: Record<string, unknown>
}

export interface AuditPage {
  total: number
  limit: number
  offset: number
  items: AuditEntry[]
}

export const listAudit = (params: { limit?: number; offset?: number; action?: string; q?: string }) =>
  api.get<AuditPage>('/audit', { params }).then(r => r.data)

export const listAuditActions = () =>
  api.get<{ actions: string[] }>('/audit/actions').then(r => r.data)
