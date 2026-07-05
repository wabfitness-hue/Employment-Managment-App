import api from './client'

export const renewContract = (personId: string, data?: { start_date?: string }) =>
  api.post(`/contracts/${personId}/renew`, data ?? {}).then(r => r.data)

export const getExpiryReport = () =>
  api.get('/contracts/report').then(r => r.data)

export const getExpiringContracts = (days = 90) =>
  api.get('/contracts/expiring', { params: { within_days: days } }).then(r => r.data)
