import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle, Copy } from 'lucide-react'
import QRCode from 'qrcode'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { setupCompany, setupAdmin, setupComplete } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { getMe } from '../api/auth'

const steps = ['Company', 'Admin Account', 'Scan QR Code', 'Done']

const companySchema = z.object({ name: z.string().min(1, 'Company name required') })
const adminSchema = z.object({
  full_name: z.string().min(2, 'Full name required'),
  email: z.string().email('Valid email required'),
  password: z.string().min(12, 'Minimum 12 characters')
    .regex(/[A-Z]/, 'Needs uppercase')
    .regex(/[a-z]/, 'Needs lowercase')
    .regex(/\d/, 'Needs a number')
    .regex(/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/, 'Needs special char'),
})
const mfaSchema = z.object({ mfa_token: z.string().length(6, '6-digit code') })

export function SetupPage() {
  const [step, setStep] = useState(0)
  const [adminId, setAdminId] = useState('')
  const [mfaUri, setMfaUri] = useState('')
  const [mfaSecret, setMfaSecret] = useState('')
  const [qrDataUrl, setQrDataUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const { setUser } = useAuthStore()
  const navigate = useNavigate()

  const companyForm = useForm({ resolver: zodResolver(companySchema) })
  const adminForm = useForm({ resolver: zodResolver(adminSchema) })
  const mfaForm = useForm({ resolver: zodResolver(mfaSchema) })

  // Generate QR code locally whenever the provisioning URI changes
  useEffect(() => {
    if (!mfaUri) return
    QRCode.toDataURL(mfaUri, { width: 220, margin: 2 })
      .then(url => setQrDataUrl(url))
      .catch(() => setQrDataUrl(''))
  }, [mfaUri])

  async function onCompany(data: { name: string }) {
    setError('')
    try {
      await setupCompany({ name: data.name })
      setStep(1)
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Error saving company')
    }
  }

  async function onAdmin(data: { full_name: string; email: string; password: string }) {
    setError('')
    try {
      const res = await setupAdmin(data)
      setAdminId(res.admin_id)
      setMfaUri(res.mfa_provisioning_uri)
      setMfaSecret(res.mfa_secret ?? '')
      setStep(2)
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Error creating account')
    }
  }

  async function onMfa(data: { mfa_token: string }) {
    setError('')
    try {
      const res = await setupComplete(adminId, data.mfa_token)
      localStorage.setItem('access_token', res.access_token)
      localStorage.setItem('refresh_token', res.refresh_token)
      const user = await getMe()
      setUser(user)
      setStep(3)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? ''
      if (detail.toLowerCase().includes('already completed')) {
        // Setup succeeded on a previous attempt — go to login
        navigate('/login', { replace: true })
        return
      }
      setError('Invalid code — please check your authenticator app and try again.')
    }
  }

  function copySecret() {
    navigator.clipboard.writeText(mfaSecret).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-blue-700 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        {/* Step indicator */}
        <div className="px-8 pt-8 pb-6 border-b border-gray-100">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">First-time setup</h1>
          <div className="flex items-center gap-2">
            {steps.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                  ${i < step ? 'bg-green-500 text-white' : i === step ? 'bg-blue-700 text-white' : 'bg-gray-200 text-gray-500'}`}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span className={`text-xs hidden sm:block ${i === step ? 'text-gray-900 font-medium' : 'text-gray-400'}`}>{s}</span>
                {i < steps.length - 1 && <div className="w-6 h-px bg-gray-200" />}
              </div>
            ))}
          </div>
        </div>

        <div className="p-8">
          {error && <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">{error}</div>}

          {/* Step 0: Company */}
          {step === 0 && (
            <form onSubmit={companyForm.handleSubmit(onCompany)} className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold mb-1">Company name</h2>
                <p className="text-sm text-gray-500 mb-4">This appears on all ID cards.</p>
              </div>
              <Input label="Company name" required
                error={companyForm.formState.errors.name?.message as string}
                {...companyForm.register('name')} />
              <Button type="submit" className="w-full" loading={companyForm.formState.isSubmitting}>Continue</Button>
            </form>
          )}

          {/* Step 1: Admin account */}
          {step === 1 && (
            <form onSubmit={adminForm.handleSubmit(onAdmin)} className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold mb-1">Administrator account</h2>
                <p className="text-sm text-gray-500 mb-4">This is the super_admin who controls the system.</p>
              </div>
              <Input label="Full name" required
                error={adminForm.formState.errors.full_name?.message as string}
                {...adminForm.register('full_name')} />
              <Input label="Email address" type="email" required
                error={adminForm.formState.errors.email?.message as string}
                {...adminForm.register('email')} />
              <Input label="Password" type="password" required
                hint="12+ chars, upper, lower, number, special"
                error={adminForm.formState.errors.password?.message as string}
                {...adminForm.register('password')} />
              <Button type="submit" className="w-full" loading={adminForm.formState.isSubmitting}>Create account</Button>
            </form>
          )}

          {/* Step 2: Scan QR */}
          {step === 2 && (
            <form onSubmit={mfaForm.handleSubmit(onMfa)} className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold mb-1">Set up authenticator</h2>
                <p className="text-sm text-gray-500 mb-4">
                  Open <strong>Google Authenticator</strong>, <strong>Authy</strong>, or any TOTP app and scan the QR code below.
                </p>
              </div>

              {/* QR code — generated locally, no internet needed */}
              <div className="flex justify-center">
                {qrDataUrl
                  ? <img src={qrDataUrl} alt="MFA QR Code" className="border rounded-lg p-2 w-[220px] h-[220px]" />
                  : <div className="w-[220px] h-[220px] border rounded-lg flex items-center justify-center text-gray-400 text-sm">Generating QR…</div>
                }
              </div>

              {/* Manual entry fallback */}
              {mfaSecret && (
                <div className="rounded-lg bg-gray-50 border border-gray-200 p-3">
                  <p className="text-xs text-gray-500 mb-1">Can't scan? Enter this code manually in your app:</p>
                  <div className="flex items-center gap-2">
                    <code className="text-sm font-mono text-gray-900 break-all flex-1">{mfaSecret}</code>
                    <button type="button" onClick={copySecret}
                      className="shrink-0 p-1 rounded hover:bg-gray-200 transition-colors"
                      title="Copy secret">
                      {copied ? <CheckCircle className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4 text-gray-500" />}
                    </button>
                  </div>
                </div>
              )}

              <Input label="6-digit code from your authenticator app" type="text" inputMode="numeric" maxLength={6} required
                error={mfaForm.formState.errors.mfa_token?.message as string}
                {...mfaForm.register('mfa_token')} />
              <Button type="submit" className="w-full" loading={mfaForm.formState.isSubmitting}>Verify and finish</Button>
            </form>
          )}

          {/* Step 3: Done */}
          {step === 3 && (
            <div className="text-center space-y-4">
              <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
              <h2 className="text-xl font-bold">Setup complete!</h2>
              <p className="text-gray-500">Your system is ready. You can now add employees and contractors.</p>
              <Button className="w-full" onClick={() => navigate('/dashboard')}>Go to dashboard</Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
