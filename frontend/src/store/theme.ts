import { create } from 'zustand'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme'

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

/** Resolve a mode to the actual effective appearance. */
function resolve(mode: ThemeMode): 'light' | 'dark' {
  return mode === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : mode
}

/** Toggle the `dark` class on <html> so Tailwind's dark: variants apply. */
function apply(mode: ThemeMode) {
  const dark = resolve(mode) === 'dark'
  document.documentElement.classList.toggle('dark', dark)
}

function stored(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch {
    return 'system'  // localStorage unavailable (private mode / non-browser)
  }
}

function persist(mode: ThemeMode) {
  try { localStorage.setItem(STORAGE_KEY, mode) } catch { /* ignore */ }
}

interface ThemeState {
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

export const useThemeStore = create<ThemeState>((set) => ({
  mode: stored(),
  setMode: (mode) => {
    persist(mode)
    apply(mode)
    set({ mode })
  },
}))

/**
 * Initialise the theme on app start: apply the stored mode immediately and,
 * while in "system" mode, follow OS-level light/dark changes live.
 */
export function initTheme() {
  apply(stored())
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (stored() === 'system') apply('system')
  })
}
