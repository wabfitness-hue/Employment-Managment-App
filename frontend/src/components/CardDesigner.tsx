import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, CheckCircle } from 'lucide-react'
import { Button } from './ui/Button'
import { CardVisual } from './ui/CardVisual'
import { getCardDesign, updateCardDesign } from '../api/companies'
import type { CardDesign, CardTypeDesign, CardFont, CardPreview } from '../types'

const BG_SWATCHES = [
  '#1E40AF', '#0E7490', '#047857', '#4D7C0F', '#B45309',
  '#EA5B0C', '#B91C1C', '#BE185D', '#7E22CE', '#4338CA',
  '#334155', '#111827', '#6B7280', '#78350F', '#14532D',
]

const ACCENT_SWATCHES = ['#F4C833', '#FB923C', '#4ADE80', '#38BDF8', '#F472B6', '#C4B5FD', '#E5E7EB', '#94A3B8']

const BAND_SWATCHES = ['#111827', '#FFFFFF', '#1E40AF', '#EA5B0C', '#047857', '#B91C1C']

const COMPANY_SWATCHES = ['#FFFFFF', '#111827', '#F4C833', '#FDE68A', '#38BDF8', '#4ADE80']

const FONTS: Array<{ value: CardFont; label: string; css: string }> = [
  { value: 'helvetica', label: 'Helvetica (modern)', css: 'Helvetica, Arial, sans-serif' },
  { value: 'times', label: 'Times (classic serif)', css: '"Times New Roman", Times, serif' },
  { value: 'courier', label: 'Courier (typewriter)', css: '"Courier New", Courier, monospace' },
]

const DEFAULTS: CardDesign = {
  employee: { bg_colour: '#1E40AF', text_colour: '#FFFFFF', accent_colour: '#F4C833', band_colour: '', company_colour: '', font: 'helvetica' },
  contractor: { bg_colour: '#EA5B0C', text_colour: '#FFFFFF', accent_colour: '#F4C833', band_colour: '', company_colour: '', font: 'helvetica' },
}

const SAMPLE_EMPLOYEE: CardPreview = {
  person_id: '', person_type: 'employee', employee_id: 'A00001',
  full_name: 'Sample Employee', job_title: 'Job Title', department: 'Department',
  floor: '1', company_name: 'Your Company', contract_end: '2031-01-01',
  has_photo: false, is_contractor: false,
}

const SAMPLE_CONTRACTOR: CardPreview = {
  ...SAMPLE_EMPLOYEE, person_type: 'contractor', is_contractor: true,
  employee_id: 'B00001', full_name: 'Sample Contractor', company_name: 'Contractor Company',
}

function SwatchRow({ colours, value, onChange }: { colours: string[]; value: string; onChange: (c: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {colours.map(c => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={`w-7 h-7 rounded-md border-2 transition-transform hover:scale-110 ${
            value.toUpperCase() === c.toUpperCase() ? 'border-gray-900 ring-2 ring-offset-1 ring-gray-400' : 'border-white shadow'
          }`}
          style={{ background: c }}
          title={c}
        />
      ))}
      <input
        type="color"
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-7 h-7 rounded-md cursor-pointer border border-gray-300 p-0.5 ml-1"
        title="Custom colour"
      />
      <span className="font-mono text-[11px] text-gray-400 uppercase ml-1">{value}</span>
    </div>
  )
}

// Swatch row with an "Auto" option (empty string = inherit / auto-derive).
function OptionalColourRow({ colours, value, onChange, autoLabel }: {
  colours: string[]; value: string; onChange: (c: string) => void; autoLabel: string
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => onChange('')}
        className={`px-3 h-7 rounded-md border-2 text-xs font-medium transition-colors ${
          !value ? 'border-gray-900 bg-gray-900 text-white' : 'border-gray-300 text-gray-600 hover:border-gray-400'
        }`}
        title={autoLabel}
      >
        Auto
      </button>
      {colours.map(c => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={`w-7 h-7 rounded-md border-2 transition-transform hover:scale-110 ${
            (value || '').toUpperCase() === c.toUpperCase() ? 'border-gray-900 ring-2 ring-offset-1 ring-gray-400' : 'border-white shadow'
          }`}
          style={{ background: c }}
          title={c}
        />
      ))}
      <input
        type="color"
        value={value || '#000000'}
        onChange={e => onChange(e.target.value)}
        className="w-7 h-7 rounded-md cursor-pointer border border-gray-300 p-0.5 ml-1"
        title="Custom colour"
      />
      <span className="font-mono text-[11px] text-gray-400 uppercase ml-1">{value || 'auto'}</span>
    </div>
  )
}

export function CardDesigner({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: saved } = useQuery({ queryKey: ['card-design'], queryFn: getCardDesign })
  const [design, setDesign] = useState<CardDesign>(DEFAULTS)
  const [tab, setTab] = useState<'employee' | 'contractor'>('employee')
  const [loaded, setLoaded] = useState(false)
  const [savedFlash, setSavedFlash] = useState(false)

  useEffect(() => {
    if (saved && !loaded) { setDesign(saved); setLoaded(true) }
  }, [saved, loaded])

  const saveMutation = useMutation({
    mutationFn: () => updateCardDesign(design),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['card-design'] })
      qc.invalidateQueries({ queryKey: ['card-preview'] })
      setSavedFlash(true)
      setTimeout(() => setSavedFlash(false), 2000)
    },
  })

  const current = design[tab]
  function patch(p: Partial<CardTypeDesign>) {
    setDesign(d => ({ ...d, [tab]: { ...d[tab], ...p } }))
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl p-6 max-h-[92vh] overflow-y-auto w-full max-w-4xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Card designer</h2>
            <p className="text-xs text-gray-500">Design how printed ID cards look — colours, text and font</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        {/* Type tabs */}
        <div className="flex gap-1 mb-5 bg-gray-100 rounded-lg p-1 w-fit">
          {(['employee', 'contractor'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
                tab === t ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {t} cards
            </button>
          ))}
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Controls */}
          <div className="space-y-5">
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Card colour</p>
              <SwatchRow colours={BG_SWATCHES} value={current.bg_colour} onChange={c => patch({ bg_colour: c })} />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">
                Top &amp; bottom band <span className="text-xs font-normal text-gray-400">(edge strips)</span>
              </p>
              <OptionalColourRow
                colours={BAND_SWATCHES}
                value={current.band_colour}
                onChange={c => patch({ band_colour: c })}
                autoLabel="Automatically darken the card colour"
              />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">
                Company name colour <span className="text-xs font-normal text-gray-400">(on the top band)</span>
              </p>
              <OptionalColourRow
                colours={COMPANY_SWATCHES}
                value={current.company_colour}
                onChange={c => patch({ company_colour: c })}
                autoLabel="Same as the main text colour"
              />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Text colour</p>
              <SwatchRow colours={['#FFFFFF', '#111827', '#F1F5F9', '#FDE68A']} value={current.text_colour} onChange={c => patch({ text_colour: c })} />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Accent colour <span className="text-xs font-normal text-gray-400">(ID number, stripe, badge)</span></p>
              <SwatchRow colours={ACCENT_SWATCHES} value={current.accent_colour} onChange={c => patch({ accent_colour: c })} />
            </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Text type</p>
              <div className="space-y-1.5">
                {FONTS.map(f => (
                  <button
                    key={f.value}
                    type="button"
                    onClick={() => patch({ font: f.value })}
                    className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                      current.font === f.value
                        ? 'border-blue-500 bg-blue-50 text-blue-900'
                        : 'border-gray-200 text-gray-700 hover:border-gray-300'
                    }`}
                    style={{ fontFamily: f.css }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Live preview */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Live preview</p>
            <div className="origin-top-left scale-[0.78]" style={{ height: 303 * 0.78, width: 480 * 0.78 }}>
              <CardVisual
                preview={tab === 'employee' ? SAMPLE_EMPLOYEE : SAMPLE_CONTRACTOR}
                design={current}
              />
            </div>
            <p className="text-xs text-gray-400 mt-3">
              Header and footer bands shade automatically darker than the card colour. Design applies to all {tab} cards when printed.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-gray-100">
          {savedFlash && <span className="text-xs text-green-600 flex items-center gap-1"><CheckCircle className="h-3.5 w-3.5" /> Design saved</span>}
          <Button variant="secondary" size="sm" onClick={onClose}>Close</Button>
          <Button size="sm" loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>Save design</Button>
        </div>
      </div>
    </div>
  )
}
