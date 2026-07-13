import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Wifi, WifiOff, DoorOpen, DoorClosed } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { useBridgeStore } from '../store/bridge'
import { lookupByNfc, getPhotoUrl } from '../api/people'
import { AuthImg } from '../components/ui/AuthImg'

type Result = {
  granted: boolean
  name: string
  reason: string | null
  direction: 'in' | 'out'
  photo: boolean
  personId: string
} | null

/**
 * Live door/kiosk screen. Listens for taps from the connected bridge reader and
 * shows a large, unambiguous granted/denied result — this is what actually turns
 * a physical tap into a real building in/out event (recorded server-side).
 */
export function DoorPage() {
  const { status, nfc, setOnTap } = useBridgeStore()
  const [result, setResult] = useState<Result>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setOnTap(async (uid, direction) => {
      setBusy(true)
      try {
        const res = await lookupByNfc(uid, direction)
        setResult({
          granted: res.access_granted,
          name: res.person.full_name,
          reason: res.denied_reason,
          direction,
          photo: res.person.has_photo,
          personId: res.person.id,
        })
      } catch {
        setResult({
          granted: false, name: 'Unknown card', reason: 'Card not recognised',
          direction, photo: false, personId: '',
        })
      } finally {
        setBusy(false)
      }
    })
    return () => setOnTap(undefined)
  }, [setOnTap])

  // Auto-clear the result after a few seconds so the screen is ready for the next tap.
  useEffect(() => {
    if (!result) return
    const t = setTimeout(() => setResult(null), 5000)
    return () => clearTimeout(t)
  }, [result])

  const direction = nfc.direction ?? 'in'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Door</h1>
        <div className="flex items-center gap-2 text-sm">
          {status === 'connected' ? (
            <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
              <Wifi className="h-4 w-4" /> Reader connected
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-gray-400">
              <WifiOff className="h-4 w-4" /> {status === 'connecting' ? 'Connecting…' : 'Not connected'}
            </span>
          )}
        </div>
      </div>

      <Card className="flex flex-col items-center justify-center py-16 min-h-[420px]">
        {!result ? (
          <div className="flex flex-col items-center gap-4 text-gray-400">
            {direction === 'in' ? <DoorOpen className="h-20 w-20" /> : <DoorClosed className="h-20 w-20" />}
            <p className="text-lg font-medium">
              {status === 'connected' ? 'Waiting for a tap…' : 'Connect the bridge to start scanning'}
            </p>
            <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
              This reader: {direction === 'in' ? 'Entry' : 'Exit'}
            </span>
            {busy && <p className="text-sm">Checking…</p>}
          </div>
        ) : (
          <div className={`flex flex-col items-center gap-4 ${result.granted ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
            {result.photo && result.personId && (
              <AuthImg
                src={getPhotoUrl(result.personId)}
                alt={result.name}
                className="w-24 h-24 rounded-full object-cover border-4 border-current"
              />
            )}
            {result.granted ? <CheckCircle2 className="h-20 w-20" /> : <XCircle className="h-20 w-20" />}
            <p className="text-2xl font-bold">{result.granted ? 'Access Granted' : 'Access Denied'}</p>
            <p className="text-lg text-gray-700 dark:text-gray-200">{result.name}</p>
            {!result.granted && result.reason && (
              <p className="text-sm text-gray-500 dark:text-gray-400">{result.reason}</p>
            )}
            <span className="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
              {result.direction === 'in' ? 'Entering' : 'Leaving'}
            </span>
          </div>
        )}
      </Card>
    </div>
  )
}
