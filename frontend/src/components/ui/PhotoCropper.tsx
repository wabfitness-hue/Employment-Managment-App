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

/** Output size of the cropped square (backend downsizes to 400×400). */
const OUTPUT = 600

function centeredSquare(width: number, height: number): PixelCrop {
  const size = Math.min(width, height) * 0.8
  return {
    unit: 'px',
    width: size,
    height: size,
    x: (width - size) / 2,
    y: (height - size) / 2,
  }
}

async function toBase64(image: HTMLImageElement, crop: PixelCrop): Promise<string> {
  // Crop coords are relative to the displayed image; scale up to natural pixels.
  const scaleX = image.naturalWidth / image.width
  const scaleY = image.naturalHeight / image.height

  const canvas = document.createElement('canvas')
  canvas.width = OUTPUT
  canvas.height = OUTPUT
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, OUTPUT, OUTPUT)
  ctx.drawImage(
    image,
    crop.x * scaleX, crop.y * scaleY, crop.width * scaleX, crop.height * scaleY,
    0, 0, OUTPUT, OUTPUT,
  )
  return canvas.toDataURL('image/jpeg', 0.92).split(',')[1]
}

/**
 * Interactive crop for ID photos. A square selection box the user can drag to
 * move and resize from any corner (aspect locked to 1:1 so the output stays
 * square — matching the backend's 400×400 storage). Frame head & shoulders.
 */
export function PhotoCropper({ imageSrc, onDone, onCancel }: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [crop, setCrop] = useState<Crop>()
  const [completed, setCompleted] = useState<PixelCrop>()
  const [saving, setSaving] = useState(false)

  function onImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const { width, height } = e.currentTarget
    const initial = centeredSquare(width, height)
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
          aspect={1}
          keepSelection
          minWidth={40}
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
        Drag a corner to resize the square, or drag the middle to move it. Frame the head and shoulders.
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
