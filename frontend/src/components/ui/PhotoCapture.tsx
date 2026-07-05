import { useRef, useState, useCallback } from 'react'
import { Camera, Upload, X, RefreshCw } from 'lucide-react'
import { Button } from './Button'
import { AuthImg } from './AuthImg'
import { PhotoCropper } from './PhotoCropper'

interface Props {
  currentUrl?: string
  onBase64: (b64: string) => void
}

export function PhotoCapture({ currentUrl, onBase64 }: Props) {
  const [mode, setMode] = useState<'idle' | 'camera' | 'crop' | 'preview'>('idle')
  const [cropSrc, setCropSrc] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [clearedExisting, setClearedExisting] = useState(false)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState('')
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const startCamera = useCallback(async () => {
    setCameraError('')
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } })
      setStream(s)
      setMode('camera')
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = s
          videoRef.current.play()
        }
      }, 50)
    } catch {
      setCameraError('Camera not available — please upload a photo instead.')
    }
  }, [])

  function stopCamera() {
    stream?.getTracks().forEach(t => t.stop())
    setStream(null)
  }

  function capture() {
    if (!videoRef.current || !canvasRef.current) return
    const v = videoRef.current
    const c = canvasRef.current
    c.width = v.videoWidth
    c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    const dataUrl = c.toDataURL('image/jpeg', 0.92)
    stopCamera()
    // Send to the cropper so the user can frame head & shoulders.
    setCropSrc(dataUrl)
    setMode('crop')
  }

  function retake() {
    setPreview(null)
    setMode('idle')
  }

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
    stopCamera()
    setPreview(null)
    setMode('idle')
    setClearedExisting(true)
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
      {/* Preview / video / placeholder */}
      <div className="relative w-40 h-40 rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-800 border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center">
        {mode === 'camera' ? (
          <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
        ) : preview ? (
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
        {(preview || (currentUrl && !clearedExisting)) && mode !== 'camera' && (
          <button onClick={clear} type="button"
            className="absolute top-1 right-1 bg-black/50 rounded-full p-1 text-white hover:bg-black/70">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Hidden canvas for capture */}
      <canvas ref={canvasRef} className="hidden" />

      {cameraError && <p className="text-xs text-red-600 text-center">{cameraError}</p>}

      {/* Controls */}
      {mode === 'idle' && (
        <div className="flex gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={startCamera}>
            <Camera className="h-4 w-4 mr-1" /> Camera
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4 mr-1" /> Upload
          </Button>
        </div>
      )}

      {mode === 'camera' && (
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={capture}>
            <Camera className="h-4 w-4 mr-1" /> Take photo
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => { stopCamera(); setMode('idle') }}>
            Cancel
          </Button>
        </div>
      )}

      {mode === 'preview' && (
        <Button type="button" variant="secondary" size="sm" onClick={retake}>
          <RefreshCw className="h-4 w-4 mr-1" /> Retake / change
        </Button>
      )}

      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onFileChange} />
    </div>
  )
}
