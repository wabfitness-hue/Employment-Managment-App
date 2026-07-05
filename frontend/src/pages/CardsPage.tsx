import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Eye, X, Palette } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PersonTypeBadge } from '../components/ui/Badge'
import { CardVisual } from '../components/ui/CardVisual'
import { CardDesigner } from '../components/CardDesigner'
import { listPeople } from '../api/people'
import { downloadCard, downloadBulkCards, getCardPreview } from '../api/cards'

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export function CardsPage() {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [designerOpen, setDesignerOpen] = useState(false)

  const { data: people = [] } = useQuery({ queryKey: ['people'], queryFn: () => listPeople({ status: 'active' }) })

  const { data: preview, isLoading: previewLoading, error: previewError } = useQuery({
    queryKey: ['card-preview', previewId],
    queryFn: () => getCardPreview(previewId!),
    enabled: !!previewId,
  })

  function toggle(id: string) {
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  function selectAll() { setSelected(new Set(people.map(p => p.id))) }
  function clearAll() { setSelected(new Set()) }

  async function downloadSingle(id: string, employeeId: string) {
    const blob = await downloadCard(id)
    saveBlob(blob, `${employeeId}.pdf`)
  }

  async function downloadBulk() {
    if (selected.size === 0) return
    setBulkLoading(true)
    try {
      const blob = await downloadBulkCards([...selected])
      saveBlob(blob, `cards-bulk-${new Date().toISOString().slice(0,10)}.pdf`)
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">ID Cards</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{selected.size} selected</p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" size="sm" onClick={() => setDesignerOpen(true)}>
            <Palette className="h-4 w-4" /> Card designer
          </Button>
          <Button variant="secondary" size="sm" onClick={selected.size === people.length ? clearAll : selectAll}>
            {selected.size === people.length ? 'Deselect all' : 'Select all'}
          </Button>
          <Button size="sm" loading={bulkLoading} disabled={selected.size === 0} onClick={downloadBulk}>
            <Download className="h-4 w-4" /> Download bulk PDF ({selected.size})
          </Button>
        </div>
      </div>

      <Card padding={false}>
        <div className="divide-y divide-gray-100">
          {people.map(p => (
            <div key={p.id} className="flex items-center gap-4 px-6 py-3 hover:bg-gray-50 dark:hover:bg-gray-800">
              <input
                type="checkbox"
                checked={selected.has(p.id)}
                onChange={() => toggle(p.id)}
                className="w-4 h-4 rounded accent-blue-600"
              />
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 dark:text-gray-100">{p.full_name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{p.employee_id}</span>
                  <PersonTypeBadge type={p.person_type} />
                  <span className="text-xs text-gray-400">{p.job_title}</span>
                </div>
              </div>
              <Button variant="secondary" size="sm" onClick={() => setPreviewId(p.id)}>
                <Eye className="h-3.5 w-3.5" /> Preview
              </Button>
              <Button variant="secondary" size="sm" onClick={() => downloadSingle(p.id, p.employee_id)}>
                <Download className="h-3.5 w-3.5" /> PDF
              </Button>
            </div>
          ))}
          {people.length === 0 && (
            <p className="text-sm text-gray-400 px-6 py-12 text-center">No active people to print cards for.</p>
          )}
        </div>
      </Card>

      {designerOpen && <CardDesigner onClose={() => setDesignerOpen(false)} />}

      {previewId && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setPreviewId(null)}
        >
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Card preview</h2>
              <button onClick={() => setPreviewId(null)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            {previewLoading && (
              <div className="w-[480px] h-[303px] flex items-center justify-center text-sm text-gray-400">
                Loading preview…
              </div>
            )}
            {previewError != null && (
              <div className="w-[480px] h-[303px] flex items-center justify-center text-sm text-red-500 text-center px-8">
                Couldn't load the card preview — this person may not have an active contract.
              </div>
            )}
            {preview && <CardVisual preview={preview} />}
            {preview && (
              <div className="flex justify-end gap-3">
                <Button variant="secondary" size="sm" onClick={() => setPreviewId(null)}>Close</Button>
                <Button size="sm" onClick={() => downloadSingle(preview.person_id, preview.employee_id)}>
                  <Download className="h-3.5 w-3.5" /> Download PDF
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
