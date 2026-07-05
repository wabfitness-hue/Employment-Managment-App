import type { CardPreview, CardTypeDesign } from '../../types'
import { AuthImg } from './AuthImg'
import { getPhotoUrl } from '../../api/people'

// On-screen replica of the printed CR80 ID card (85.6 × 54 mm).
// Mirrors the layout in backend/app/services/cards/generator.py.

const BLUE = '#1E40AF'
const ORANGE = '#EA5B0C'
const GOLD = '#F4C833'
const WHITE = '#FFFFFF'

export const FONT_CSS: Record<string, string> = {
  helvetica: 'Helvetica, Arial, sans-serif',
  times: '"Times New Roman", Times, serif',
  courier: '"Courier New", Courier, monospace',
}

// Darker shade for the header/footer strips (matches the PDF generator)
export function darken(hex: string, factor = 0.62): string {
  const h = hex.replace('#', '')
  const parts = [0, 2, 4].map(i => Math.round(parseInt(h.slice(i, i + 2), 16) * factor))
  return '#' + parts.map(p => p.toString(16).padStart(2, '0')).join('')
}

export function CardVisual({ preview, design }: { preview: CardPreview; design?: CardTypeDesign }) {
  const bg = design?.bg_colour ?? preview.bg_colour ?? (preview.is_contractor ? ORANGE : BLUE)
  const text = design?.text_colour ?? preview.text_colour ?? WHITE
  const accent = design?.accent_colour ?? preview.accent_colour ?? GOLD
  const font = FONT_CSS[design?.font ?? preview.font ?? 'helvetica'] ?? FONT_CSS.helvetica
  const band = design ? design.band_colour : preview.band_colour
  const strip = band && band.length > 0 ? band : darken(bg)
  const companyColour = (design ? design.company_colour : preview.company_colour) || text

  return (
    <div
      className="rounded-xl overflow-hidden shadow-lg select-none"
      style={{ width: 480, height: 303, background: bg, fontFamily: font, color: text }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4" style={{ height: 50, background: strip }}>
        <span className="font-bold tracking-wide" style={{ fontSize: 18, color: companyColour }}>
          {preview.company_name.toUpperCase()}
        </span>
        <span
          className="font-bold rounded px-3 py-1"
          style={{ background: accent, color: '#1a1a1a', fontSize: 13 }}
        >
          {preview.is_contractor ? 'CONTRACTOR' : 'EMPLOYEE'}
        </span>
      </div>

      {/* Body */}
      <div className="flex px-4 items-start" style={{ height: 208, paddingTop: 14 }}>
        {/* Photo */}
        <div
          className="flex-shrink-0 border-2 bg-gray-300 flex items-center justify-center overflow-hidden"
          style={{ width: 124, height: 158, borderColor: text }}
        >
          {preview.has_photo ? (
            <AuthImg
              src={getPhotoUrl(preview.person_id)}
              alt={preview.full_name}
              className="w-full h-full object-cover"
              fallback={<span className="text-gray-500 text-xs font-medium">NO PHOTO</span>}
            />
          ) : (
            <span className="text-gray-500 text-xs font-medium text-center leading-tight">NO<br />PHOTO</span>
          )}
        </div>

        {/* Accent stripe */}
        <div className="flex-shrink-0 mx-3" style={{ width: 3, height: 158, background: accent }} />

        {/* Details */}
        <div className="min-w-0 flex-1">
          <p className="font-bold truncate" style={{ fontSize: 24, lineHeight: 1.15 }}>{preview.full_name}</p>
          <p className="font-bold" style={{ fontSize: 21, color: accent, marginTop: 6 }}>{preview.employee_id}</p>
          <p className="truncate" style={{ fontSize: 18, marginTop: 8 }}>{preview.job_title}</p>
          <p className="truncate" style={{ fontSize: 16, marginTop: 6 }}>
            {preview.department}{preview.floor ? `  |  Floor ${preview.floor}` : ''}
          </p>
          {preview.is_contractor && (
            <p className="font-bold truncate" style={{ fontSize: 15, color: accent, marginTop: 6 }}>
              {preview.company_name.toUpperCase()}
            </p>
          )}
        </div>
      </div>

      {/* Footer — plain band; access and expiry live in the profile, not on the card */}
      <div style={{ height: 45, background: strip }} />
    </div>
  )
}
