import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { CheckCircle, Link, Unlink, Plus, Trash2, ShieldCheck, KeyRound, Copy } from 'lucide-react'
import QRCode from 'qrcode'
import { Card, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { getPrefixes, setPrefixes, changePassword, setupMfa, enableMfa, getMe } from '../api/auth'
import { useAuthStore } from '../store/auth'
import api from '../api/client'
import type { IdPrefix } from '../types'

function SecuritySection() {
  const { user, setUser } = useAuthStore()

  // ── Change password ──
  const [curPwd, setCurPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const pwdMutation = useMutation({
    mutationFn: () => changePassword(curPwd, newPwd),
    onSuccess: () => {
      setPwdMsg({ ok: true, text: 'Password changed.' })
      setCurPwd(''); setNewPwd(''); setConfirmPwd('')
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setPwdMsg({ ok: false, text: detail ?? 'Could not change password.' })
    },
  })

  function submitPwd() {
    setPwdMsg(null)
    if (newPwd !== confirmPwd) { setPwdMsg({ ok: false, text: 'New passwords do not match.' }); return }
    if (newPwd.length < 12) { setPwdMsg({ ok: false, text: 'New password must be at least 12 characters.' }); return }
    pwdMutation.mutate()
  }

  // ── Enable MFA ──
  const [mfaSecret, setMfaSecret] = useState('')
  const [qrData, setQrData] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [mfaMsg, setMfaMsg] = useState('')

  const startMfa = useMutation({
    mutationFn: setupMfa,
    onSuccess: async (d) => {
      setMfaSecret(d.secret)
      setMfaMsg('')
      try { setQrData(await QRCode.toDataURL(d.provisioning_uri, { width: 200, margin: 2 })) } catch { /* manual entry fallback */ }
    },
  })

  const confirmMfa = useMutation({
    mutationFn: () => enableMfa(mfaCode.trim()),
    onSuccess: async () => {
      setMfaMsg('')
      setMfaSecret(''); setQrData(''); setMfaCode('')
      const me = await getMe()
      setUser(me)
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setMfaMsg(detail ?? 'Invalid code — MFA not enabled.')
    },
  })

  return (
    <Card>
      <CardHeader title="Security" subtitle="Protect your admin account" />

      {/* MFA */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">Two-factor authentication</span>
          {user?.mfa_enabled
            ? <Badge variant="green">Enabled</Badge>
            : <Badge variant="orange">Off</Badge>}
        </div>

        {user?.mfa_enabled ? (
          <p className="text-sm text-gray-500">Your account is protected by an authenticator app.</p>
        ) : !mfaSecret ? (
          <div className="space-y-2">
            <p className="text-sm text-gray-500">Add a second step at login using an authenticator app (Google Authenticator, Microsoft Authenticator, Authy).</p>
            <Button size="sm" loading={startMfa.isPending} onClick={() => startMfa.mutate()}>
              <ShieldCheck className="h-4 w-4" /> Set up 2FA
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-600">1. Scan this with your authenticator app:</p>
            {qrData && <img src={qrData} alt="MFA QR code" className="w-44 h-44 border border-gray-200 rounded-lg" />}
            <div className="text-xs text-gray-500">
              Or enter this key manually:
              <button
                className="ml-2 font-mono text-gray-700 inline-flex items-center gap-1 hover:text-blue-600"
                onClick={() => navigator.clipboard?.writeText(mfaSecret)}
              >
                {mfaSecret} <Copy className="h-3 w-3" />
              </button>
            </div>
            <p className="text-sm text-gray-600">2. Enter the 6-digit code it shows:</p>
            <div className="flex gap-2">
              <input
                value={mfaCode}
                onChange={e => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="w-28 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono tracking-widest text-center focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
              />
              <Button size="sm" loading={confirmMfa.isPending} disabled={mfaCode.length !== 6} onClick={() => confirmMfa.mutate()}>
                Verify &amp; enable
              </Button>
            </div>
            {mfaMsg && <p className="text-xs text-red-600">{mfaMsg}</p>}
          </div>
        )}
      </div>

      {/* Change password */}
      <div className="border-t border-gray-100 pt-5">
        <div className="flex items-center gap-2 mb-3">
          <KeyRound className="h-4 w-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">Change password</span>
        </div>
        <div className="space-y-2 max-w-sm">
          <input type="password" autoComplete="current-password" value={curPwd} onChange={e => setCurPwd(e.target.value)} placeholder="Current password"
            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none" />
          <input type="password" autoComplete="new-password" value={newPwd} onChange={e => setNewPwd(e.target.value)} placeholder="New password (min 12 characters)"
            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none" />
          <input type="password" autoComplete="new-password" value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)} placeholder="Confirm new password"
            className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none" />
          {pwdMsg && <p className={`text-xs ${pwdMsg.ok ? 'text-green-600' : 'text-red-600'}`}>{pwdMsg.text}</p>}
          <Button size="sm" variant="secondary" loading={pwdMutation.isPending}
            disabled={!curPwd || !newPwd || !confirmPwd}
            onClick={submitPwd}>
            Update password
          </Button>
        </div>
      </div>
    </Card>
  )
}

function OutlookSection() {
  const [params] = useSearchParams()
  const connected = params.get('connected')

  const { data: status, refetch } = useQuery({
    queryKey: ['outlook-status'],
    queryFn: () => api.get('/outlook/status').then(r => r.data),
  })

  const disconnectMutation = useMutation({
    mutationFn: () => api.delete('/outlook/disconnect'),
    onSuccess: () => refetch(),
  })

  const scanMutation = useMutation({
    mutationFn: () => api.post('/outlook/scan'),
  })

  function handleConnect() {
    api.get('/outlook/connect').then(r => {
      window.location.href = r.data.auth_url
    })
  }

  return (
    <Card>
      <CardHeader title="Outlook / Email" subtitle="Receive photos via email attachment" />
      {connected === 'true' && (
        <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
          <CheckCircle className="h-4 w-4" /> Connected successfully!
        </div>
      )}
      {status?.connected ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge variant="green">Connected</Badge>
            <span className="text-sm text-gray-600">{status.outlook_email}</span>
          </div>
          <div className="flex gap-3">
            <Button size="sm" loading={scanMutation.isPending} onClick={() => scanMutation.mutate()}>
              Scan inbox now
            </Button>
            <Button size="sm" variant="danger" loading={disconnectMutation.isPending} onClick={() => disconnectMutation.mutate()}>
              <Unlink className="h-4 w-4" /> Disconnect
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">Connect your personal Outlook account to receive photo attachments sent to that mailbox.</p>
          <Button onClick={handleConnect}>
            <Link className="h-4 w-4" /> Connect Outlook
          </Button>
        </div>
      )}
    </Card>
  )
}

function PrefixesSection() {
  const qc = useQueryClient()
  const { data: prefixes = [] } = useQuery<IdPrefix[]>({ queryKey: ['prefixes'], queryFn: getPrefixes })
  const [editing, setEditing] = useState<IdPrefix[]>([])
  const [saveError, setSaveError] = useState('')
  function startEdit() { setEditing([...prefixes]); setSaveError('') }
  function cancelEdit() { setEditing([]); setSaveError('') }

  function update(i: number, field: keyof IdPrefix, value: string) {
    setEditing(e => e.map((p, j) => j === i ? { ...p, [field]: value } : p))
  }

  function addRow() {
    setEditing(e => [...e, { id: '', prefix: '', label: '', person_type: 'employee', next_sequence: 1, is_active: true }])
  }

  function removeRow(i: number) {
    setEditing(e => e.filter((_, j) => j !== i))
  }

  const saveMutation = useMutation({
    mutationFn: () => setPrefixes(editing.map(p => ({ prefix: p.prefix, label: p.label, person_type: p.person_type }))),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prefixes'] }); setEditing([]); setSaveError('') },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setSaveError(detail ?? 'Failed to save prefixes. Check each prefix is 1–5 uppercase letters.')
    },
  })

  const isEditing = editing.length > 0

  return (
    <Card>
      <CardHeader
        title="ID Prefixes"
        subtitle="Control the prefix codes used for employee and contractor IDs"
        action={
          isEditing ? (
            <div className="flex gap-2">
              <Button size="sm" loading={saveMutation.isPending} onClick={() => saveMutation.mutate()}>Save</Button>
              <Button size="sm" variant="secondary" onClick={cancelEdit}>Cancel</Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" onClick={startEdit}>Edit</Button>
          )
        }
      />
      {saveError && (
        <div className="mb-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">{saveError}</div>
      )}
      <p className="text-xs text-gray-400 mb-3">Prefix format: 1–5 letters (A, B, EMP, CTR…). IDs will appear as <span className="font-mono">A00001</span>, <span className="font-mono">B00001</span>, etc.</p>
      <div className="space-y-2">
        {(isEditing ? editing : prefixes).map((p, i) => (
          <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
            {isEditing ? (
              <>
                <input
                  className="w-20 px-2 py-1 rounded border border-gray-300 text-sm font-mono uppercase"
                  value={p.prefix}
                  onChange={e => update(i, 'prefix', e.target.value.toUpperCase())}
                  placeholder="PREFIX"
                />
                <input
                  className="flex-1 px-2 py-1 rounded border border-gray-300 text-sm"
                  value={p.label}
                  onChange={e => update(i, 'label', e.target.value)}
                  placeholder="Label"
                />
                <select
                  className="px-2 py-1 rounded border border-gray-300 text-sm"
                  value={p.person_type}
                  onChange={e => update(i, 'person_type', e.target.value)}
                >
                  <option value="employee">Employee</option>
                  <option value="contractor">Contractor</option>
                </select>
                <button onClick={() => removeRow(i)} className="text-red-500 hover:text-red-700 p-1">
                  <Trash2 className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                <span className="font-mono text-sm w-20 text-gray-900">{p.prefix}</span>
                <span className="flex-1 text-sm text-gray-700">{p.label}</span>
                <Badge variant={p.person_type === 'employee' ? 'blue' : 'orange'}>{p.person_type}</Badge>
              </>
            )}
          </div>
        ))}
        {isEditing && (
          <button onClick={addRow} className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 pt-2">
            <Plus className="h-4 w-4" /> Add prefix
          </button>
        )}
      </div>
    </Card>
  )
}

export function SettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      <SecuritySection />
      <OutlookSection />
      <PrefixesSection />
    </div>
  )
}
