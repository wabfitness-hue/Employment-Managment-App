import api from './client'
import type { ImportJob } from '../types'

export const previewImport = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/import/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const runImport = (jobId: string, file: File, mainCompanyId: string, skipErrors = true) => {
  const form = new FormData()
  form.append('file', file)
  form.append('job_id', jobId)
  form.append('main_company_id', mainCompanyId)
  form.append('skip_errors', String(skipErrors))
  return api.post('/import/run', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const listImportJobs = () =>
  api.get<ImportJob[]>('/import/jobs').then(r => r.data)

export const getImportJob = (id: string) =>
  api.get<ImportJob>(`/import/jobs/${id}`).then(r => r.data)

export const downloadTemplate = (fmt: 'csv' | 'xlsx' | 'docx') =>
  api.get(`/import/template/${fmt}`, { responseType: 'blob' }).then(r => r.data)
