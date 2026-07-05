import { useRef, useState, useEffect, useCallback } from 'react'
import { Camera, X } from 'lucide-react'
import { Button } from './Button'

interface Props {
  /** Called with a captured frame as a JPEG data URL (un-mirrored). */
  onCapture: (dataUrl: string) => void
  onCancel: () => void
}

/**
 * Shared webcam capture: live preview with a camera picker (when more than one
 * camera is present), a mirrored preview (natural, selfie-style) that is saved
 * UN-mirrored, and a request for a high-resolution stream for sharp ID photos.
 */
export function WebcamCapture({ onCapture, onCancel }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState<string>('')
  const [error, setError] = useState('')

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }, [])

  const start = useCallback(async (id?: string) => {
    setError('')
    stop()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          ...(id ? { deviceId: { exact: id } } : { facingMode: 'user' }),
          width: { ideal: 1280 },
          height: { ideal: 960 },
        },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }
      // Labels are only populated after permission is granted — enumerate now.
      const list = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput')
      setDevices(list)
      if (!id) {
        const active = stream.getVideoTracks()[0]?.getSettings().deviceId
        if (active) setDeviceId(active)
      }
    } catch {
      setError('Camera not available. Check permissions, or upload a photo instead.')
    }
  }, [stop])

  useEffect(() => {
    start()
    return stop  // stop the camera when unmounted
  }, [start, stop])

  function onPickDevice(e: React.ChangeEvent<HTMLSelectElement>) {
    const id = e.target.value
    setDeviceId(id)
    start(id)
  }

  function capture() {
    const v = videoRef.current
    const c = canvasRef.current
    if (!v || !c || !v.videoWidth) return
    c.width = v.videoWidth
    c.height = v.videoHeight
    // Draw normally (not mirrored) so the saved photo reads the correct way round.
    c.getContext('2d')!.drawImage(v, 0, 0)
    onCapture(c.toDataURL('image/jpeg', 0.95))
  }

  return (
    <div className="flex flex-col gap-3">
      {devices.length > 1 && (
        <select
          value={deviceId}
          onChange={onPickDevice}
          className="w-full px-3 py-2 rounded-lg border text-sm border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          {devices.map((d, i) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `Camera ${i + 1}`}
            </option>
          ))}
        </select>
      )}

      <div className="relative w-full aspect-square bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center">
        {error ? (
          <p className="text-xs text-red-400 text-center px-4">{error}</p>
        ) : (
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
            style={{ transform: 'scaleX(-1)' }}  // mirror preview only
          />
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />

      <div className="flex gap-3">
        <Button className="flex-1" onClick={capture} disabled={!!error}>
          <Camera className="h-4 w-4" /> Take photo
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          <X className="h-4 w-4" /> Cancel
        </Button>
      </div>
    </div>
  )
}
