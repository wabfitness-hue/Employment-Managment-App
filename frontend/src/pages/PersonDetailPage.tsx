import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Edit, CreditCard, RefreshCw, Camera, Upload, Nfc, Power, Trash2, AlertTriangle, IdCard, Check, LogIn, LogOut, ChevronLeft, ChevronRight } from 'lucide-react'
import { WebcamCapture } from '../components/ui/WebcamCapture'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { PhotoCropper } from '../components/ui/PhotoCropper'
import { PersonTypeBadge, StatusBadge, ExpiryBadge } from '../components/ui/Badge'
import { AuthImg } from '../components/ui/AuthImg'
import { getPerson, getPhotoUrl, uploadPhotoBase64, assignNfc, setPersonStatus, deletePerson, setCardStatus, issueTempCard, returnTempCard, getAccessLog } from '../api/people'
import { CARD_STATUSES } from '../types'
import { renewContract } from '../api/contracts'
import { downloadCard } from '../api/cards'
import { listPrinters } from '../api/printers'
import { useBridgeStore } from '../store/bridge'

function InfoRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-gray-500 dark:text-gray-400 w-36 shrink-0">{label}</span>
      <span className="text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  )
}

const ACCESS_LOG_PAGE_SIZE = 10

function BuildingAccessSection({ personId }: { personId: string }) {
  const [offset, setOffset] = useState(0)
  const { data, isLoading } = useQuery({
    queryKey: ['access-log', personId, offset],
    queryFn: () => getAccessLog(personId, { limit: ACCESS_LOG_PAGE_SIZE, offset }),
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + ACCESS_LOG_PAGE_SIZE, total)

  return (
    <Card>
      <CardHeader title="Building Access" subtitle="Date and time this person entered or left, via the door reader" />
      {isLoading ? (
        <p className="text-sm text-gray-400 py-4 text-center">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No recorded taps yet.</p>
      ) : (
        <div className="space-y-1">
          {items.map(e => {
            const dt = new Date(e.timestamp)
            const Icon = e.direction === 'in' ? LogIn : LogOut
            return (
              <div key={e.id} className="flex items-center gap-3 py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                <Icon className={`h-4 w-4 shrink-0 ${e.granted ? (e.direction === 'in' ? 'text-green-600' : 'text-blue-500') : 'text-red-500'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-900 dark:text-gray-100">
                    {e.direction === 'in' ? 'Entered' : 'Left'}
                    <span className="text-gray-400 dark:text-gray-500 font-normal"> · {dt.toLocaleDateString()} at {dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </p>
                  {!e.granted && e.reason && (
                    <p className="text-xs text-red-500">Denied — {e.reason}</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {total > ACCESS_LOG_PAGE_SIZE && (
        <div className="flex items-center justify-between mt-3 text-sm text-gray-500 dark:text-gray-400">
          <span>{from}–{to} of {total}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - ACCESS_LOG_PAGE_SIZE))}>
              <ChevronLeft className="h-4 w-4" /> Prev
            </Button>
            <Button size="sm" variant="secondary" disabled={to >= total} onClick={() => setOffset(offset + ACCESS_LOG_PAGE_SIZE)}>
              Next <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

export function PersonDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [photoModal, setPhotoModal] = useState(false)
  const [webcamActive, setWebcamActive] = useState(false)
  const [cropSrc, setCropSrc] = useState<string | null>(null)
  const [nfcModal, setNfcModal] = useState(false)
  const [nfcStatus, setNfcStatus] = useState<'idle' | 'waiting' | 'done' | 'error'>('idle')
  const [deleteModal, setDeleteModal] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [cardStatus, setCardStatusState] = useState('active')
  const [cardNote, setCardNote] = useState('')
  const [cardSaved, setCardSaved] = useState(false)
  const [tempUid, setTempUid] = useState('')
  const [tempReading, setTempReading] = useState(false)
  const [tempError, setTempError] = useState('')
  const [printModal, setPrintModal] = useState(false)
  const [selectedPrinterId, setSelectedPrinterId] = useState('')
  const [printing, setPrinting] = useState(false)
  const [printMsg, setPrintMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: person, isLoading } = useQuery({
    queryKey: ['person', id],
    queryFn: () => getPerson(id!),
    enabled: !!id,
  })

  const renewMutation = useMutation({
    mutationFn: () => renewContract(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['person', id] }),
  })

  const statusMutation = useMutation({
    mutationFn: (status: string) => setPersonStatus(id!, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['person', id] })
      qc.invalidateQueries({ queryKey: ['people'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePerson(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['people'] })
      navigate('/people')
    },
  })

  const cardStatusMutation = useMutation({
    mutationFn: () => setCardStatus(id!, cardStatus, cardNote),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['person', id] })
      qc.invalidateQueries({ queryKey: ['people'] })
      setCardSaved(true)
      setTimeout(() => setCardSaved(false), 2000)
    },
  })

  const issueTempMutation = useMutation({
    mutationFn: () => issueTempCard(id!, tempUid.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['person', id] })
      qc.invalidateQueries({ queryKey: ['people'] })
      setTempUid('')
      setTempError('')
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setTempError(detail ?? 'Could not issue the temporary card.')
    },
  })

  const returnTempMutation = useMutation({
    mutationFn: () => returnTempCard(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['person', id] })
      qc.invalidateQueries({ queryKey: ['people'] })
    },
  })

  function readTempCard() {
    setTempError('')
    setTempReading(true)
    const reqId = crypto.randomUUID()
    setOnTap((uid: string) => {
      setTempUid(uid)
      setTempReading(false)
      setOnTap(undefined)
    })
    sendReadOnce(reqId)
    setTimeout(() => { setTempReading(false); setOnTap(undefined) }, 16000)
  }

  useEffect(() => {
    if (person) {
      setCardStatusState(person.card_status || 'active')
      setCardNote(person.card_status_note || '')
    }
  }, [person?.id, person?.card_status, person?.card_status_note])

  const { sendReadOnce, sendPrint, setOnTap, status: bridgeStatus } = useBridgeStore()

  const { data: printers = [] } = useQuery({ queryKey: ['printers'], queryFn: listPrinters })

  useEffect(() => {
    if (printers.length > 0 && !selectedPrinterId) setSelectedPrinterId(printers[0].id)
  }, [printers, selectedPrinterId])

  function handlePhotoFile(file: File) {
    // Load the file, then let the user crop to head & shoulders before upload.
    const reader = new FileReader()
    reader.onload = () => { setCropSrc(reader.result as string); setWebcamActive(false) }
    reader.readAsDataURL(file)
  }

  async function handleCroppedPhoto(b64: string) {
    await uploadPhotoBase64(id!, `data:image/jpeg;base64,${b64}`)
    qc.invalidateQueries({ queryKey: ['person', id] })
    setCropSrc(null)
    setPhotoModal(false)
  }

  function startNfcEnrol() {
    setNfcStatus('waiting')
    const reqId = crypto.randomUUID()
    setOnTap((uid: string) => {
      assignNfc(id!, uid)
        .then(() => {
          qc.invalidateQueries({ queryKey: ['person', id] })
          setNfcStatus('done')
          setOnTap(undefined)
        })
        .catch(() => { setNfcStatus('error'); setOnTap(undefined) })
    })
    sendReadOnce(reqId)
    setTimeout(() => {
      setNfcStatus(s => s === 'waiting' ? 'error' : s)
      setOnTap(undefined)
    }, 16000)
  }

  async function handleDownloadCard() {
    const blob = await downloadCard(id!)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${person?.employee_id ?? 'card'}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function blobToBase64(blob: Blob): Promise<string> {
    const buf = await blob.arrayBuffer()
    let binary = ''
    const bytes = new Uint8Array(buf)
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
    return btoa(binary)
  }

  async function handlePrintToPrinter() {
    setPrintMsg(null)
    setPrinting(true)
    try {
      const blob = await downloadCard(id!)
      const pdfB64 = await blobToBase64(blob)
      const printer = printers.find(p => p.id === selectedPrinterId)
      await sendPrint(
        pdfB64,
        crypto.randomUUID(),
        1,
        printer ? { target_type: printer.target_type, target: printer.target } : undefined,
      )
      setPrintMsg({ ok: true, text: 'Sent to printer.' })
    } catch (e: unknown) {
      setPrintMsg({ ok: false, text: e instanceof Error ? e.message : 'Print failed.' })
    } finally {
      setPrinting(false)
    }
  }

  if (isLoading) return <div className="flex items-center justify-center py-20 text-gray-400">Loading…</div>
  if (!person) return <div className="text-center py-20 text-gray-500 dark:text-gray-400">Person not found.</div>

  const c = person.current_contract

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/people')}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <div className="flex-1" />
        <Button variant="secondary" size="sm" onClick={() => navigate(`/people/${id}/edit`)}>
          <Edit className="h-4 w-4" /> Edit
        </Button>
        <Button size="sm" onClick={() => { setPrintMsg(null); setPrintModal(true) }}>
          <CreditCard className="h-4 w-4" /> Print card
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Photo + Identity */}
        <div className="space-y-4">
          <Card>
            <div className="flex flex-col items-center gap-4">
              <div className={`w-32 h-32 rounded-full overflow-hidden border-4 ${person.person_type === 'employee' ? 'border-blue-200' : 'border-orange-200'}`}>
                {person.has_photo ? (
                  <AuthImg src={getPhotoUrl(id!)} alt={person.full_name} className="w-full h-full object-cover" />
                ) : (
                  <div className={`w-full h-full flex items-center justify-center text-4xl font-bold ${person.person_type === 'employee' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700'}`}>
                    {person.full_name[0]}
                  </div>
                )}
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{person.full_name}</h2>
                <p className="text-gray-500 dark:text-gray-400 text-sm">{person.job_title}</p>
                <p className="font-mono text-xs text-gray-400 mt-1">{person.employee_id}</p>
              </div>
              <div className="flex gap-2 flex-wrap justify-center">
                <PersonTypeBadge type={person.person_type} />
                <StatusBadge status={person.status} />
              </div>
              {person.card_status && person.card_status !== 'active' && (
                <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-3 py-1">
                  <IdCard className="h-3.5 w-3.5" />
                  {CARD_STATUSES[person.card_status] ?? person.card_status}
                  {person.card_status_note && <span className="text-amber-500 font-normal">· {person.card_status_note}</span>}
                </div>
              )}
              <Button variant="secondary" size="sm" className="w-full" onClick={() => setPhotoModal(true)}>
                <Camera className="h-4 w-4" /> {person.has_photo ? 'Change photo' : 'Add photo'}
              </Button>
            </div>
          </Card>

          {/* NFC */}
          <Card>
            <CardHeader title="NFC Card" />
            {person.nfc_uid ? (
              <div className="space-y-2">
                <p className="text-xs text-gray-500 dark:text-gray-400">Enrolled UID</p>
                <p className="font-mono text-sm bg-gray-50 dark:bg-gray-900 rounded px-3 py-2">{person.nfc_uid}</p>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">No NFC card enrolled.</p>
            )}
            <Button
              variant="secondary"
              size="sm"
              className="w-full mt-3"
              disabled={bridgeStatus !== 'connected'}
              onClick={() => { setNfcModal(true); startNfcEnrol() }}
            >
              <Nfc className="h-4 w-4" />
              {person.nfc_uid ? 'Re-enrol card' : 'Enrol NFC card'}
            </Button>
            {bridgeStatus !== 'connected' && (
              <p className="text-xs text-gray-400 mt-1 text-center">Bridge agent must be running</p>
            )}
          </Card>

          {/* Card status */}
          <Card>
            <CardHeader title="Card status" subtitle="Why this card's access differs from normal" />

            {person.temp_nfc_uid ? (
              /* A temporary card is currently issued */
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 space-y-2">
                  <p className="text-sm font-medium text-blue-800 flex items-center gap-1.5">
                    <IdCard className="h-4 w-4" /> Temporary card active
                  </p>
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-500 dark:text-gray-400">Temp card</span>
                      <span className="font-mono text-blue-700">{person.temp_nfc_uid}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500 dark:text-gray-400">Permanent card</span>
                      <span className="font-mono text-gray-400 line-through">{person.nfc_uid ?? '—'}</span>
                    </div>
                  </div>
                  <p className="text-xs text-blue-600">The permanent card is blocked at readers until returned.</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  loading={returnTempMutation.isPending}
                  onClick={() => returnTempMutation.mutate()}
                >
                  <RefreshCw className="h-4 w-4" /> Return temp card &amp; restore permanent
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <select
                  value={cardStatus}
                  onChange={e => setCardStatusState(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm bg-white dark:bg-gray-800 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                >
                  {Object.entries(CARD_STATUSES).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>

                {cardStatus === 'temporary' ? (
                  /* Forgot card → issue a temporary one */
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Scan or enter the spare card to issue as a temporary. The permanent card ({person.nfc_uid ?? 'none'}) will be marked forgotten and blocked until returned.
                    </p>
                    <div className="flex gap-2">
                      <input
                        value={tempUid}
                        onChange={e => setTempUid(e.target.value.toUpperCase())}
                        placeholder="Temp card UID"
                        className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm font-mono uppercase focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                      />
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={bridgeStatus !== 'connected' || tempReading}
                        onClick={readTempCard}
                        title={bridgeStatus !== 'connected' ? 'Bridge agent must be running' : 'Tap card on reader'}
                      >
                        <Nfc className="h-4 w-4" /> {tempReading ? '…' : 'Tap'}
                      </Button>
                    </div>
                    {tempError && <p className="text-xs text-red-600">{tempError}</p>}
                    <Button
                      size="sm"
                      className="w-full"
                      loading={issueTempMutation.isPending}
                      disabled={!tempUid.trim()}
                      onClick={() => issueTempMutation.mutate()}
                    >
                      <IdCard className="h-4 w-4" /> Issue temporary card
                    </Button>
                  </div>
                ) : (
                  <>
                    <input
                      value={cardNote}
                      onChange={e => setCardNote(e.target.value)}
                      placeholder="Note (e.g. faulty reader chip, returned Fri)"
                      className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      className="w-full"
                      loading={cardStatusMutation.isPending}
                      disabled={cardStatus === (person.card_status || 'active') && cardNote === (person.card_status_note || '')}
                      onClick={() => cardStatusMutation.mutate()}
                    >
                      {cardSaved ? <><Check className="h-4 w-4" /> Saved</> : <><IdCard className="h-4 w-4" /> Update card status</>}
                    </Button>
                  </>
                )}
              </div>
            )}
          </Card>

          {/* Manage / danger zone */}
          <Card>
            <CardHeader title="Manage" />
            <div className="space-y-2">
              {person.status === 'active' ? (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  loading={statusMutation.isPending}
                  onClick={() => statusMutation.mutate('inactive')}
                >
                  <Power className="h-4 w-4" /> Deactivate
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  loading={statusMutation.isPending}
                  onClick={() => statusMutation.mutate('active')}
                >
                  <Power className="h-4 w-4" /> Reactivate
                </Button>
              )}
              <button
                onClick={() => { setConfirmText(''); setDeleteModal(true) }}
                className="w-full flex items-center justify-center gap-2 text-sm text-red-600 border border-red-200 rounded-lg py-1.5 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" /> Permanently delete
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Deactivating keeps the record and hides them from active lists. Deleting removes the person, photo and history for good.
            </p>
          </Card>
        </div>

        {/* Details */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader title="Details" />
            <div className="space-y-2.5">
              <InfoRow label="Job title" value={person.job_title} />
              <InfoRow label="Email" value={person.email} />
              <InfoRow label="Phone" value={person.phone} />
              <InfoRow label="Department" value={person.department} />
              <InfoRow label="Floor" value={person.floor} />
              <InfoRow label="Company" value={person.company_name} />
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Contract"
              action={
                c && !c.is_expired ? null : (
                  <Button size="sm" variant="secondary" loading={renewMutation.isPending} onClick={() => renewMutation.mutate()}>
                    <RefreshCw className="h-4 w-4" /> Renew
                  </Button>
                )
              }
            />
            {c ? (
              <div className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <ExpiryBadge level={c.expiry_warning_level} />
                  <span className="text-sm text-gray-600 dark:text-gray-300">{c.days_remaining}d remaining</span>
                </div>
                <InfoRow label="Type" value={c.contract_type === 'employee_5yr' ? '5-year Employee' : '6-month Contractor'} />
                <InfoRow label="Start" value={new Date(c.start_date).toLocaleDateString('en-GB')} />
                <InfoRow label="End" value={new Date(c.end_date).toLocaleDateString('en-GB')} />
                <InfoRow label="Renewals" value={String(c.renewal_count)} />
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">No active contract.</p>
            )}
          </Card>

          {person.access && (
            <Card>
              <CardHeader title="Access" />
              <div className="space-y-2.5">
                <InfoRow label="Profile" value={person.access.profile_name ?? 'Direct assignment'} />
                <InfoRow label="Zones" value={`${person.access.zone_count} zone${person.access.zone_count !== 1 ? 's' : ''}`} />
                {person.access.has_time_restriction && (
                  <>
                    <InfoRow label="Days" value={person.access.allowed_days ?? undefined} />
                    <InfoRow label="Hours" value={person.access.access_start && person.access.access_end ? `${person.access.access_start} – ${person.access.access_end}` : undefined} />
                  </>
                )}
              </div>
            </Card>
          )}

          <BuildingAccessSection personId={id!} />
        </div>
      </div>

      {/* Photo Modal */}
      <Modal open={photoModal} onClose={() => { setPhotoModal(false); setWebcamActive(false); setCropSrc(null) }} title="Update photo">
        <div className="space-y-4">
          {cropSrc ? (
            <PhotoCropper
              imageSrc={cropSrc}
              onDone={handleCroppedPhoto}
              onCancel={() => setCropSrc(null)}
            />
          ) : webcamActive ? (
            <WebcamCapture
              onCapture={(dataUrl) => { setCropSrc(dataUrl); setWebcamActive(false) }}
              onCancel={() => setWebcamActive(false)}
            />
          ) : (
            <div className="flex flex-col gap-3">
              <Button onClick={() => setWebcamActive(true)}>
                <Camera className="h-4 w-4" /> Use webcam
              </Button>
              <Button variant="secondary" onClick={() => fileRef.current?.click()}>
                <Upload className="h-4 w-4" /> Upload file
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) handlePhotoFile(f) }}
              />
            </div>
          )}
        </div>
      </Modal>

      {/* NFC Modal */}
      <Modal open={nfcModal} onClose={() => { setNfcModal(false); setNfcStatus('idle') }} title="Enrol NFC card">
        <div className="text-center space-y-4 py-4">
          {nfcStatus === 'waiting' && (
            <>
              <div className="w-20 h-20 mx-auto rounded-full border-4 border-blue-200 border-t-blue-600 animate-spin" />
              <p className="text-gray-600 dark:text-gray-300">Hold the NFC card near the reader…</p>
              <p className="text-xs text-gray-400">Timeout in 15 seconds</p>
            </>
          )}
          {nfcStatus === 'done' && (
            <>
              <div className="text-5xl">✓</div>
              <p className="text-green-600 font-medium">Card enrolled successfully!</p>
              <Button onClick={() => { setNfcModal(false); setNfcStatus('idle') }}>Done</Button>
            </>
          )}
          {nfcStatus === 'error' && (
            <>
              <div className="text-5xl">✗</div>
              <p className="text-red-600">Failed or timed out. Please try again.</p>
              <Button variant="secondary" onClick={() => { setNfcStatus('idle'); startNfcEnrol() }}>Retry</Button>
            </>
          )}
        </div>
      </Modal>

      {/* Print Card Modal */}
      <Modal open={printModal} onClose={() => setPrintModal(false)} title="Print card">
        <div className="space-y-4">
          {printers.length > 0 && (
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Printer</label>
              <select
                value={selectedPrinterId}
                onChange={e => setSelectedPrinterId(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-800 text-sm"
              >
                {printers.map(p => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
          )}

          {printers.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No printers configured yet. Add one in Settings, or download the PDF and print it manually.
            </p>
          )}

          {bridgeStatus !== 'connected' && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              Bridge agent not connected — printing directly isn't available right now. You can still download the PDF.
            </p>
          )}

          {printMsg && (
            <p className={`text-sm ${printMsg.ok ? 'text-green-600' : 'text-red-600'}`}>{printMsg.text}</p>
          )}

          <div className="flex gap-3">
            <Button
              className="flex-1"
              loading={printing}
              disabled={bridgeStatus !== 'connected' || printers.length === 0}
              onClick={handlePrintToPrinter}
            >
              <CreditCard className="h-4 w-4" /> Print
            </Button>
            <Button variant="secondary" onClick={handleDownloadCard}>
              Download PDF
            </Button>
          </div>
        </div>
      </Modal>

      {/* Permanent delete confirmation */}
      <Modal open={deleteModal} onClose={() => setDeleteModal(false)} title="Permanently delete">
        <div className="space-y-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-red-50 border border-red-200">
            <AlertTriangle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">
              This permanently removes <span className="font-medium">{person.full_name}</span> ({person.employee_id}),
              their photo and all contract history. This cannot be undone.
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
              Type <span className="font-mono font-medium">{person.employee_id}</span> to confirm:
            </p>
            <input
              autoFocus
              value={confirmText}
              onChange={e => setConfirmText(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm font-mono uppercase focus:border-red-400 focus:ring-1 focus:ring-red-400 outline-none"
              placeholder={person.employee_id}
            />
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" size="sm" onClick={() => setDeleteModal(false)}>Cancel</Button>
            <Button
              variant="danger"
              size="sm"
              loading={deleteMutation.isPending}
              disabled={confirmText.trim().toUpperCase() !== person.employee_id.toUpperCase()}
              onClick={() => deleteMutation.mutate()}
            >
              <Trash2 className="h-4 w-4" /> Delete permanently
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
