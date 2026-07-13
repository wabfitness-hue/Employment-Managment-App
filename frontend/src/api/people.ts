import api from './client'
import type { Person, PersonListItem, PersonFilter } from '../types'

export const listPeople = (filters?: PersonFilter & { limit?: number; offset?: number }) =>
  api.get<PersonListItem[]>('/people', { params: filters }).then(r => r.data)

export const exportPeopleCsv = (filters?: PersonFilter & { search?: string }) =>
  api.get('/people/export.csv', { params: filters, responseType: 'blob' }).then(r => r.data as Blob)

export const getPerson = (id: string) =>
  api.get<Person>(`/people/${id}`).then(r => r.data)

export const createPerson = (data: Record<string, unknown>) =>
  api.post<Person>('/people', data).then(r => r.data)

export const updatePerson = (id: string, data: Record<string, unknown>) =>
  api.patch<Person>(`/people/${id}`, data).then(r => r.data)

export const setPersonStatus = (id: string, status: string, reason?: string) =>
  api.post(`/people/${id}/status`, { status, reason }).then(r => r.data)

export const deletePerson = (id: string) =>
  api.delete(`/people/${id}`).then(r => r.data)

export const setCardStatus = (id: string, card_status: string, note?: string) =>
  api.post(`/people/${id}/card-status`, { card_status, note }).then(r => r.data)

export const issueTempCard = (id: string, nfc_uid: string) =>
  api.post<Person>(`/people/${id}/temp-card`, { nfc_uid }).then(r => r.data)

export const returnTempCard = (id: string) =>
  api.delete<Person>(`/people/${id}/temp-card`).then(r => r.data)

export const assignNfc = (id: string, nfc_uid: string) =>
  api.post(`/people/${id}/nfc`, { nfc_uid }).then(r => r.data)

export interface NfcLookupResult {
  access_granted: boolean
  denied_reason: string | null
  card_status: string
  person: Person
}

export const lookupByNfc = (uid: string, direction?: 'in' | 'out') =>
  api.get<NfcLookupResult>(`/people/nfc/${uid}`, { params: direction ? { direction } : undefined }).then(r => r.data)

export interface AccessLogEntry {
  id: string
  direction: 'in' | 'out'
  granted: boolean
  reason: string | null
  timestamp: string
}

export interface AccessLogPage {
  total: number
  limit: number
  offset: number
  items: AccessLogEntry[]
}

export const getAccessLog = (personId: string, params?: { limit?: number; offset?: number }) =>
  api.get<AccessLogPage>(`/people/${personId}/access-log`, { params }).then(r => r.data)

export const getDepartments = () =>
  api.get<string[]>('/people/departments').then(r => r.data)

export const uploadPhoto = (id: string, file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/photos/${id}/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const uploadPhotoBase64 = (id: string, base64: string) =>
  api.post(`/photos/${id}/webcam`, { image_data: base64 }).then(r => r.data)

// Relative to the `api` axios client's baseURL ('/api/v1') — used with AuthImg, not raw <img src>
export const getPhotoUrl = (id: string) => `/photos/${id}`
