import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CardVisual, darken, FONT_CSS } from './CardVisual'
import type { CardPreview } from '../../types'

const sample: CardPreview = {
  person_id: '00000000-0000-0000-0000-000000000001',
  person_type: 'employee',
  employee_id: 'A0012345',
  full_name: 'Jane Doe',
  job_title: 'Engineer',
  department: 'Engineering',
  company_name: 'Acme',
  contract_end: '2030-01-01',
  has_photo: false,
  is_contractor: false,
}

describe('darken', () => {
  it('darkens a hex colour toward black', () => {
    expect(darken('#ffffff', 0.5)).toBe('#808080')
    expect(darken('#ffffff', 0)).toBe('#000000')
  })

  it('returns a 7-char hex string', () => {
    expect(darken('#1E40AF')).toMatch(/^#[0-9a-f]{6}$/)
  })
})

describe('FONT_CSS', () => {
  it('maps known fonts and has a helvetica fallback', () => {
    expect(FONT_CSS.helvetica).toBeTruthy()
    expect(FONT_CSS.times).toBeTruthy()
    expect(FONT_CSS.courier).toBeTruthy()
  })
})

describe('CardVisual', () => {
  it('renders the person and company details', () => {
    render(<CardVisual preview={sample} />)
    expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    expect(screen.getByText('A0012345')).toBeInTheDocument()
    expect(screen.getByText('Engineer')).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()      // company shown upper-cased
    expect(screen.getByText('EMPLOYEE')).toBeInTheDocument()
  })

  it('shows CONTRACTOR for contractor cards', () => {
    render(<CardVisual preview={{ ...sample, is_contractor: true }} />)
    expect(screen.getByText('CONTRACTOR')).toBeInTheDocument()
  })
})
