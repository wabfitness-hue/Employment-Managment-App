import { describe, it, expect, beforeEach } from 'vitest'
import { useThemeStore } from './theme'

describe('theme store', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('applies the dark class when set to dark', () => {
    useThemeStore.getState().setMode('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(useThemeStore.getState().mode).toBe('dark')
  })

  it('removes the dark class when set to light', () => {
    useThemeStore.getState().setMode('dark')
    useThemeStore.getState().setMode('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(useThemeStore.getState().mode).toBe('light')
  })

  it('records the chosen mode in the store', () => {
    useThemeStore.getState().setMode('system')
    expect(useThemeStore.getState().mode).toBe('system')
  })
})
