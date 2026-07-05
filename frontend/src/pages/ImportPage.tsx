import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Upload, Download, CheckCircle, XCircle } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { previewImport, runImport, listImportJobs, downloadTemplate } from '../api/imports'
import type { ImportJob } from '../types'

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export function ImportPage() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportJob | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ImportJob | null>(null)
  const [error, setError] = useState('')

  const { data: jobs = [], refetch } = useQuery({ queryKey: ['import-jobs'], queryFn: listImportJobs })

  async function handleFilePick(f: File) {
    setPreview(null); setResult(null); setError('')
    const MAX_MB = 10
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_MB} MB limit`)
      return
    }
    setFile(f)
    try {
      const p = await previewImport(f)
      setPreview(p)
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Preview failed')
    }
  }

  async function handleRun() {
    if (!file || !preview) return
    setRunning(true); setError('')
    try {
      const r = await runImport(preview.id, file, '', true)
      setResult(r)
      refetch()
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Import failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Data Import</h1>
        <div className="flex gap-2">
          {(['csv', 'xlsx', 'docx'] as const).map(fmt => (
            <Button key={fmt} variant="secondary" size="sm" onClick={() => downloadTemplate(fmt).then(b => saveBlob(b, `template.${fmt}`))}>
              <Download className="h-3.5 w-3.5" /> {fmt.toUpperCase()}
            </Button>
          ))}
        </div>
      </div>

      {/* Upload zone */}
      <Card>
        <CardHeader title="Upload file" subtitle="Supported formats: CSV, XLSX, DOCX (max 10 MB)" />
        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors"
          onClick={() => fileRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFilePick(f) }}
        >
          <Upload className="h-10 w-10 text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">{file ? file.name : 'Click or drag to upload'}</p>
          <p className="text-sm text-gray-400 mt-1">CSV, XLSX, or DOCX</p>
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.docx" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFilePick(f) }} />
        </div>
      </Card>

      {error && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>}

      {/* Preview */}
      {preview && !result && (
        <Card>
          <CardHeader title="Preview" subtitle={`${preview.records_found} row${preview.records_found !== 1 ? 's' : ''} found`} />
          <div className="flex gap-6 mb-4">
            <div className="flex items-center gap-2 text-green-700">
              <CheckCircle className="h-5 w-5" />
              <span className="font-semibold">{preview.preview_data?.valid_count ?? 0}</span>
              <span className="text-sm">valid</span>
            </div>
            <div className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              <span className="font-semibold">{preview.preview_data?.invalid_count ?? 0}</span>
              <span className="text-sm">invalid</span>
            </div>
          </div>
          {(preview.preview_data?.errors?.length ?? 0) > 0 && (
            <details className="mb-4">
              <summary className="cursor-pointer text-sm text-red-600 font-medium">Show errors</summary>
              <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                {preview.preview_data!.errors.map((e, i) => (
                  <div key={i} className="text-xs bg-red-50 rounded p-2">
                    <span className="font-medium">Row {e.row}:</span> {e.errors.join('; ')}
                  </div>
                ))}
              </div>
            </details>
          )}
          <div className="flex gap-3">
            <Button onClick={handleRun} loading={running} disabled={(preview.preview_data?.valid_count ?? 0) === 0}>
              Import {preview.preview_data?.valid_count ?? 0} records
            </Button>
            <Button variant="secondary" onClick={() => { setFile(null); setPreview(null); setError('') }}>Cancel</Button>
          </div>
        </Card>
      )}

      {/* Result */}
      {result && (
        <Card>
          <div className="text-center space-y-2 py-4">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
            <h3 className="text-lg font-semibold">Import complete</h3>
            <p className="text-gray-600">{result.records_imported} imported, {result.records_skipped} skipped</p>
            <Button onClick={() => { setFile(null); setPreview(null); setResult(null) }}>Import another</Button>
          </div>
        </Card>
      )}

      {/* History */}
      {jobs.length > 0 && (
        <Card padding={false}>
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-lg font-semibold">Import history</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {jobs.map(job => (
              <div key={job.id} className="flex items-center gap-3 px-6 py-3 text-sm">
                <span className="font-medium flex-1">{job.filename ?? 'Unnamed'}</span>
                <span className="text-gray-500">{new Date(job.created_at).toLocaleDateString('en-GB')}</span>
                <span className="text-gray-500">{job.records_imported}/{job.records_found}</span>
                <Badge variant={job.status === 'completed' ? 'green' : job.status === 'failed' ? 'red' : 'gray'}>
                  {job.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
