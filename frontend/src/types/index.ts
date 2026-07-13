// ── Auth ──────────────────────────────────────────────────────────────────────

export type UserRole = 'super_admin' | 'hr_admin' | 'it_admin' | 'manager'

export interface AuthUser {
  id: string
  email: string
  display_name: string
  role: UserRole
  mfa_enabled: boolean
  department_scope?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  mfa_required?: boolean
}

// ── People ────────────────────────────────────────────────────────────────────

export type PersonType = 'employee' | 'contractor'
export type PersonStatus = 'active' | 'inactive' | 'suspended' | 'terminated'

export interface Contract {
  id: string
  contract_type: 'employee_5yr' | 'contractor_6mo'
  start_date: string
  end_date: string
  is_current: boolean
  days_remaining: number
  is_expired: boolean
  expiry_warning_level: 'none' | 'notice' | 'warning' | 'critical' | 'expired'
  renewal_count: number
}

export interface AccessSummary {
  profile_name: string | null
  has_time_restriction: boolean
  allowed_days: string | null
  access_start: string | null
  access_end: string | null
  zone_count: number
}

export interface Person {
  id: string
  employee_id: string
  first_name: string
  last_name: string
  full_name: string
  email: string
  phone?: string
  person_type: PersonType
  status: PersonStatus
  card_status: string
  card_status_note?: string | null
  job_title: string
  department: string
  floor?: string
  company_id: string
  prefix_id: string
  company_name?: string
  nfc_uid?: string
  temp_nfc_uid?: string | null
  has_photo: boolean
  current_contract: Contract | null
  access: AccessSummary | null
  created_at: string
}

export interface PersonListItem {
  id: string
  employee_id: string
  full_name: string
  email: string
  person_type: PersonType
  status: PersonStatus
  card_status: string
  job_title: string
  department: string
  company_name?: string
  has_photo: boolean
  contract_end?: string
  expiry_warning: string
}

export const CARD_STATUSES: Record<string, string> = {
  active: 'Card active',
  forgotten: 'Forgot card',
  temporary: 'Temporary card issued',
  lost: 'Lost card',
  stolen: 'Stolen card',
  faulty: 'Faulty card',
  on_leave: 'On leave',
  returned: 'Card returned',
  not_issued: 'No card issued',
}

export interface PersonFilter {
  search?: string
  person_type?: PersonType
  status?: PersonStatus
  department?: string
  expiry_warning?: string
}

// ── Company ───────────────────────────────────────────────────────────────────

export interface Company {
  id: string
  name: string
  is_main_company: boolean
  card_background_colour: string
  card_text_colour: string
}

// ── ID Prefixes ───────────────────────────────────────────────────────────────

export interface IdPrefix {
  id: string
  prefix: string
  label: string
  person_type: PersonType
  next_sequence: number
  is_active: boolean
}

// ── Access control ────────────────────────────────────────────────────────────

export interface AccessZone {
  id: string
  code: string
  name: string
  floor?: string
  sort_order: number
}

export interface AccessProfile {
  id: string
  name: string
  description?: string
  default_for_prefix_id?: string
}

// ── Import ────────────────────────────────────────────────────────────────────

export interface ImportJob {
  id: string
  source_type: 'csv' | 'xlsx' | 'docx'
  filename?: string
  status: 'pending' | 'processing' | 'review' | 'completed' | 'failed' | 'cancelled'
  records_found: number
  records_imported: number
  records_skipped: number
  created_at: string
  completed_at?: string
  errors?: Array<{ row: number; errors: string[] }>
  preview_data?: {
    valid_count: number
    invalid_count: number
    valid_sample: Record<string, unknown>[]
    errors: Array<{ row: number; errors: string[]; raw: Record<string, unknown> }>
  }
}

// ── Card preview ──────────────────────────────────────────────────────────────

export interface CardPreview {
  person_id: string
  person_type: PersonType
  employee_id: string
  full_name: string
  job_title: string
  department: string
  floor?: string
  company_name: string
  contract_end: string
  has_photo: boolean
  access_profile_name?: string
  access_days?: string
  access_start?: string
  access_end?: string
  is_contractor: boolean
  nfc_uid?: string
  bg_colour?: string | null
  text_colour?: string | null
  accent_colour?: string | null
  band_colour?: string | null
  company_colour?: string | null
  font?: string
}

export type CardFont = 'helvetica' | 'times' | 'courier'

export interface CardTypeDesign {
  bg_colour: string
  text_colour: string
  accent_colour: string
  band_colour: string
  company_colour: string
  font: CardFont
}

export interface CardDesign {
  employee: CardTypeDesign
  contractor: CardTypeDesign
}

// ── Outlook ───────────────────────────────────────────────────────────────────

export interface OutlookStatus {
  connected: boolean
  outlook_email?: string
  token_expires_at?: string
  token_expired?: boolean
  can_refresh?: boolean
}

// ── Bridge Agent ──────────────────────────────────────────────────────────────

export type BridgeStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface BridgeState {
  status: BridgeStatus
  nfc: { available: boolean; reader: string | null; direction?: 'in' | 'out' }
  printer: { available: boolean; name: string | null; type: string }
  lastTap?: string
}
