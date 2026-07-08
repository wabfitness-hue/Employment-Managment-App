import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, PersonTypeBadge } from './Badge'

describe('Badge', () => {
  it('renders its children', () => {
    render(<Badge variant="green">Enabled</Badge>)
    expect(screen.getByText('Enabled')).toBeInTheDocument()
  })

  it('PersonTypeBadge shows the person type', () => {
    render(<PersonTypeBadge type="contractor" />)
    expect(screen.getByText('Contractor')).toBeInTheDocument()
  })
})
