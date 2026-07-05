import api from './client'
import type { CardPreview } from '../types'

export const getCardPreview = (personId: string) =>
  api.get<CardPreview>(`/cards/${personId}/preview`).then(r => r.data)

export const downloadCard = (personId: string) =>
  api.get(`/cards/${personId}`, { responseType: 'blob' }).then(r => r.data)

export const downloadBulkCards = (personIds: string[]) =>
  api.post('/cards/bulk', { person_ids: personIds }, { responseType: 'blob' }).then(r => r.data)
