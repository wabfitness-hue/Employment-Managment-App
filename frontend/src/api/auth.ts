import api from './client'
import type { AuthUser, LoginResponse } from '../types'

export const login = (email: string, password: string) =>
  api.post<LoginResponse>('/auth/login', { email, password }).then(r => r.data)

export const verifyMfa = (preAuthToken: string, creds: { totp_code?: string; recovery_code?: string }) =>
  api.post<LoginResponse>(
    '/auth/mfa/verify',
    creds,
    { headers: { Authorization: `Bearer ${preAuthToken}` } },
  ).then(r => r.data)

export const getMe = () =>
  api.get<AuthUser>('/auth/me').then(r => r.data)

export const changePassword = (current: string, newPwd: string) =>
  api.post('/auth/change-password', { current_password: current, new_password: newPwd })

export const setupMfa = () =>
  api.post<{ secret: string; provisioning_uri: string }>('/auth/mfa/setup').then(r => r.data)

export const enableMfa = (totp_code: string) =>
  api.post<{ message: string; recovery_codes: string[] }>('/auth/mfa/enable', { totp_code }).then(r => r.data)

export const regenerateRecoveryCodes = () =>
  api.post<{ codes: string[]; remaining: number }>('/auth/mfa/recovery-codes').then(r => r.data)

export const getRecoveryCodesStatus = () =>
  api.get<{ configured: boolean; remaining: number }>('/auth/mfa/recovery-codes').then(r => r.data)

export const setupStatus = () =>
  api.get<{ setup_required: boolean; has_company: boolean; has_users: boolean }>('/setup/status').then(r => r.data)

export const setupCompany = (data: { name: string; card_background_colour?: string; card_text_colour?: string }) =>
  api.post('/setup/company', data).then(r => r.data)

export const setupAdmin = (data: { email: string; password: string; full_name: string }) =>
  api.post<{ admin_id: string; mfa_provisioning_uri: string; mfa_secret: string }>('/setup/admin', data).then(r => r.data)

export const setupComplete = (admin_id: string, mfa_token: string) =>
  api.post<LoginResponse>('/setup/complete', { admin_id, mfa_token }).then(r => r.data)

export const getPrefixes = () =>
  api.get('/setup/prefixes').then(r => r.data)

export const setPrefixes = (prefixes: Array<{ prefix: string; label: string; person_type: string }>) =>
  api.post('/setup/prefixes', { prefixes }).then(r => r.data)

export const quickPrefix = (prefix: string, person_type: string) =>
  api.post<{ id: string; prefix: string }>('/setup/prefixes/quick', { prefix, person_type }).then(r => r.data)
