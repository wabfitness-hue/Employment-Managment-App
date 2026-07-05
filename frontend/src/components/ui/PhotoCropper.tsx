import { useState, useCallback } from 'react'
import Cropper, { type Area } from 'react-easy-crop'
import { Button } from './Button'
import { ZoomIn, ZoomOut, Check, X } from 'lucide-react'

interface Props {
  /** Source image as a data/object URL to crop. */
  imageSrc: string
  /** Called with the cropped image as raw base64 (no data: prefix). */
  onDone: (base64: string) => void
  onCancel: () => void
}

/** Output size of the cropped square (backend downsizes to 400×400). */
const OUTPUT = 600

async function getCroppedBase64(imageSrc: string, area: Area): Promise<string> {
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = imageSrc
  })

  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT
  canvas.height = OUTPUT
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, OUTPUT, OUTPUT)
  ctx.drawImage(
    image,
    area.x, area.y, area.width, area.height,
    0, 0, OUTPUT, OUTPUT,
  )
  const dataUrl = canvas.toDataURL('image/jpeg', 0.92)
  return dataUrl.split(',')[1]
}

/**
 * Interactive crop + zoom for ID photos. Square (1:1) output so the framing the
 * user chooses is preserved by the backend (which stores a 400×400 square). An
 * oval guide helps line up a passport-style head-and-shoulders shot.
 */
export function PhotoCropper({ imageSrc, onDone, onCancel }: Props) {
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [area, setArea] = useState<Area | null>(null)
  const [saving, setSaving] = useState(false)

  const onComplete = useCallback((_: Area, pixels: Area) => setArea(pixels), [])

  async function confirm() {
    if (!area) return
    setSaving(true)
    try {
      onDone(await getCroppedBase64(imageSrc, area))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="relative w-full h-72 bg-gray-900 rounded-lg overflow-hidden">
        <Cropper
          image={imageSrc}
          crop={crop}
          zoom={zoom}
          aspect={1}
          cropShape="round"
          showGrid={false}
          onCropChange={setCrop}
          onZoomChange={setZoom}
          onCropComplete={onComplete}
        />
      </div>

      <p className="text-xs text-center text-gray-500 dark:text-gray-400">
        Drag to reposition · pinch or use the slider to zoom. Frame the head and shoulders inside the circle.
      </p>

      {/* Zoom slider */}
      <div className="flex items-center gap-3 px-1">
        <ZoomOut className="h-4 w-4 text-gray-400 shrink-0" />
        <input
          type="range"
          min={1}
          max={3}
          step={0.01}
          value={zoom}
          onChange={e => setZoom(Number(e.target.value))}
          className="w-full accent-blue-600"
          aria-label="Zoom"
        />
        <ZoomIn className="h-4 w-4 text-gray-400 shrink-0" />
      </div>

      <div className="flex gap-3">
        <Button className="flex-1" onClick={confirm} loading={saving} disabled={!area}>
          <Check className="h-4 w-4" /> Use photo
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          <X className="h-4 w-4" /> Cancel
        </Button>
      </div>
    </div>
  )
}
