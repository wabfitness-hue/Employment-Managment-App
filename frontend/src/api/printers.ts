import api from './client'

export type PrinterTargetType = 'os' | 'zebra'

export interface Printer {
  id: string
  label: string
  target_type: PrinterTargetType
  target: string
}

export const listPrinters = () =>
  api.get<Printer[]>('/printers').then(r => r.data)

export const createPrinter = (data: { label: string; target_type: PrinterTargetType; target: string }) =>
  api.post<Printer>('/printers', data).then(r => r.data)

export const deletePrinter = (id: string) =>
  api.delete(`/printers/${id}`).then(r => r.data)
