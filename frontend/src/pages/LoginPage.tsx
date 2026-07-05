import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { login, verifyMfa, getMe, setupStatus } from '../api/auth'
import { useAuthStore } from '../store/auth'

const loginSchema = z.object({
  email: z.string().email('Valid email required'),
  password: z.string().min(1, 'Password required'),
})

const mfaSchema = z.object({ mfa_token: z.string().length(6, '6-digit code required') })

type LoginForm = z.infer<typeof loginSchema>
type MfaForm = z.infer<typeof mfaSchema>

export function LoginPage() {
  const [step, setStep] = useState<'credentials' | 'mfa'>('credentials')
  const [tempToken, setTempToken] = useState('')
  const [error, setError] = useState('')
  const { setUser } = useAuthStore()
  const navigate = useNavigate()

  // Redirect to setup wizard if no admin account exists yet
  useEffect(() => {
    setupStatus().then(s => {
      if (s.setup_required) navigate('/setup', { replace: true })
    }).catch(() => {})
  }, [navigate])

  const loginForm = useForm<LoginForm>({ resolver: zodResolver(loginSchema) })
  const mfaForm = useForm<MfaForm>({ resolver: zodResolver(mfaSchema) })

  async function handleLogin(data: LoginForm) {
    setError('')
    try {
      const res = await login(data.email, data.password)
      if (res.mfa_required) {
        // pre-MFA token is returned in access_token; store it to send with MFA verify
        setTempToken(res.access_token)
        setStep('mfa')
      } else {
        localStorage.setItem('access_token', res.access_token)
        localStorage.setItem('refresh_token', res.refresh_token)
        const user = await getMe()
        setUser(user)
        navigate('/dashboard')
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Login failed. Check your credentials.')
    }
  }

  async function handleMfa(data: MfaForm) {
    setError('')
    try {
      const res = await verifyMfa(tempToken, data.mfa_token)
      localStorage.setItem('access_token', res.access_token)
      localStorage.setItem('refresh_token', res.refresh_token)
      const user = await getMe()
      setUser(user)
      navigate('/dashboard')
    } catch {
      setError('Invalid or expired MFA code.')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-blue-700">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-700 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white text-2xl font-bold">EMS</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Employee Management</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            {step === 'credentials' ? 'Sign in to your account' : 'Enter your authenticator code'}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            {error}
          </div>
        )}

        {step === 'credentials' ? (
          <form onSubmit={loginForm.handleSubmit(handleLogin)} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              autoComplete="email"
              required
              error={loginForm.formState.errors.email?.message}
              {...loginForm.register('email')}
            />
            <Input
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              error={loginForm.formState.errors.password?.message}
              {...loginForm.register('password')}
            />
            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={loginForm.formState.isSubmitting}
            >
              Sign in
            </Button>
          </form>
        ) : (
          <form onSubmit={mfaForm.handleSubmit(handleMfa)} className="space-y-4">
            <Input
              label="Authenticator code"
              type="text"
              inputMode="numeric"
              maxLength={6}
              autoComplete="one-time-code"
              required
              error={mfaForm.formState.errors.mfa_token?.message}
              {...mfaForm.register('mfa_token')}
            />
            <Button
              type="submit"
              className="w-full"
              size="lg"
              loading={mfaForm.formState.isSubmitting}
            >
              Verify
            </Button>
            <button
              type="button"
              onClick={() => setStep('credentials')}
              className="w-full text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700"
            >
              ← Back to login
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
