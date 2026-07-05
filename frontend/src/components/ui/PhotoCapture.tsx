import { useRef, useState } from 'react'
import { Camera, Upload, X, RefreshCw } from 'lucide-react'
import { Button } from './Button'
import { AuthImg } from './AuthImg'
import { PhotoCropper } from './PhotoCropper'
import { WebcamCapture } from './WebcamCapture'

interface Props {
  currentUrl?: string
  onBase64: (b64: string) => void
}

export function PhotoCapture({ currentUrl, onBase64 }: Props) {
  const [mode, setMode] = useState<'idle' | 'camera' | 'crop' | 'preview'>('idle')
  const [cropSrc, setCropSrc] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [clearedExisting, setClearedExisting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (!f) return
    if (f.size > 5 * 1024 * 1024) { alert('Photo must be under 5 MB'); return }
    const reader = new FileReader()
    reader.onload = () => { setCropSrc(reader.result as string); setMode('crop') }
    reader.readAsDataURL(f)
    e.target.value = ''
  }

  function onCropped(b64: string) {
    setPreview(`data:image/jpeg;base64,${b64}`)
    setCropSrc(null)
    setMode('preview')
    onBase64(b64)
  }

  function clear() {
    setPreview(null)
    setMode('idle')
    setClearedExisting(true)
  }

  if (mode === 'camera') {
    return (
      <div className="w-full max-w-sm">
        <WebcamCapture
          onCapture={(dataUrl) => { setCropSrc(dataUrl); setMode('crop') }}
          onCancel={() => setMode('idle')}
        />
      </div>
    )
  }

  if (mode === 'crop' && cropSrc) {
    return (
      <div className="w-full max-w-sm">
        <PhotoCropper
          imageSrc={cropSrc}
          onDone={onCropped}
          onCancel={() => { setCropSrc(null); setMode('idle') }}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-3">
      {/* Preview / placeholder */}
      <div className="relative w-40 h-40 rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-800 border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center">
        {preview ? (
          <img src={preview} alt="ID photo" className="w-full h-full object-cover" />
        ) : currentUrl && !clearedExisting ? (
          <AuthImg
            src={currentUrl}
            alt="ID photo"
            className="w-full h-full object-cover"
            fallback={
              <div className="flex flex-col items-center gap-2 text-gray-400">
                <Camera className="h-10 w-10" />
                <span className="text-xs text-center">No photo</span>
              </div>
            }
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-gray-400">
            <Camera className="h-10 w-10" />
            <span className="text-xs text-center">No photo</span>
          </div>
        )}

        {/* Clear button */}
        {(preview || (currentUrl && !clearedExisting)) && (
          <button onClick={clear} type="button"
            className="absolute top-1 right-1 bg-black/50 rounded-full p-1 text-white hover:bg-black/70">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Controls */}
      {mode !== 'preview' ? (
        <div className="flex gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={() => setMode('camera')}>
            <Camera className="h-4 w-4 mr-1" /> Camera
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4 mr-1" /> Upload
          </Button>
        </div>
      ) : (
        <Button type="button" variant="secondary" size="sm" onClick={() => setMode('idle')}>
          <RefreshCw className="h-4 w-4 mr-1" /> Retake / change
        </Button>
      )}

      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onFileChange} />
    </div>
  )
}
