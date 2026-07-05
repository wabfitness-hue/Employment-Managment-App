import api from './client'

export interface Company {
  id: string
  name: string
  is_main_company: boolean
}

export const listCompanies = () =>
  api.get<Company[]>('/companies').then(r => r.data)

export const createCompany = (name: string) =>
  api.post<Company>('/companies', { name }).then(r => r.data)

import type { CardDesign } from '../types'

export const getCardDesign = () =>
  api.get<CardDesign>('/companies/card-design').then(r => r.data)

export const updateCardDesign = (design: CardDesign) =>
  api.put<CardDesign>('/companies/card-design', design).then(r => r.data)
