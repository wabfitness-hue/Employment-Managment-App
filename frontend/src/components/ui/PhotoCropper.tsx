import { useState, useRef } from 'react'
import ReactCrop, { type Crop, type PixelCrop } from 'react-image-crop'
import 'react-image-crop/dist/ReactCrop.css'
import { Button } from './Button'
import { Check, X } from 'lucide-react'

interface Props {
  /** Source image as a data/object URL to crop. */
  imageSrc: string
  /** Called with the cropped image as raw base64 (no data: prefix). */
  onDone: (base64: string) => void
  onCancel: () => void
}

/** Portrait aspect of the ID card photo slot (22×28mm) — passport proportions. */
const PHOTO_ASPECT = 22 / 28
/** Cap the longest side of the exported image (backend downsizes further). */
const MAX_SIDE = 800

function centeredPortrait(width: number, height: number): PixelCrop {
  let h = height * 0.85
  let w = h * PHOTO_ASPECT
  if (w > width * 0.9) { w = width * 0.9; h = w / PHOTO_ASPECT }
  return { unit: 'px', width: w, height: h, x: (width - w) / 2, y: (height - h) / 2 }
}

async function toBase64(image: HTMLImageElement, crop: PixelCrop): Promise<string> {
  // Crop coords are relative to the displayed image; scale up to natural pixels.
  const scaleX = image.naturalWidth / image.width
  const scaleY = image.naturalHeight / image.height
  const cw = crop.width * scaleX
  const ch = crop.height * scaleY

  const longest = Math.max(cw, ch)
  const scale = longest > MAX_SIDE ? MAX_SIDE / longest : 1
  const ow = Math.round(cw * scale)
  const oh = Math.round(ch * scale)

  const canvas = document.createElement('canvas')
  canvas.width = ow
  canvas.height = oh
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, ow, oh)
  ctx.drawImage(image, crop.x * scaleX, crop.y * scaleY, cw, ch, 0, 0, ow, oh)
  return canvas.toDataURL('image/jpeg', 0.92).split(',')[1]
}

/**
 * Interactive crop for ID photos. A portrait selection box (passport shape,
 * matching the card's photo slot) that the user can move and resize by dragging
 * any corner or edge. Aspect is kept portrait so it always fills the card slot
 * without distortion.
 */
export function PhotoCropper({ imageSrc, onDone, onCancel }: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [crop, setCrop] = useState<Crop>()
  const [completed, setCompleted] = useState<PixelCrop>()
  const [saving, setSaving] = useState(false)

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { width, height } = e.currentTarget
    const initial = centeredPortrait(width, height)
    setCrop(initial)
    setCompleted(initial)
  }

  async function confirm() {
    if (!imgRef.current || !completed?.width) return
    setSaving(true)
    try {
      onDone(await toBase64(imgRef.current, completed))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-center bg-gray-900 rounded-lg overflow-hidden">
        <ReactCrop
          crop={crop}
          onChange={c => setCrop(c)}
          onComplete={c => setCompleted(c)}
          aspect={PHOTO_ASPECT}
          keepSelection
          minWidth={30}
        >
          <img
            ref={imgRef}
            src={imageSrc}
            alt="Crop"
            onLoad={onImageLoad}
            className="max-h-80 w-auto object-contain select-none"
          />
        </ReactCrop>
      </div>

      <p className="text-xs text-center text-gray-500 dark:text-gray-400">
        Drag any corner or edge to resize the box, or drag the middle to move it. Frame the head and shoulders.
      </p>

      <div className="flex gap-3">
        <Button className="flex-1" onClick={confirm} loading={saving} disabled={!completed?.width}>
          <Check className="h-4 w-4" /> Use photo
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={saving}>
          <X className="h-4 w-4" /> Cancel
        </Button>
      </div>
    </div>
  )
}
