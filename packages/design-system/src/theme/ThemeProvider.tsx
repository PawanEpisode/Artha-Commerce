import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react'

import {
  applyResolvedTheme,
  DEFAULT_THEME_PREFERENCE,
  parseThemePreference,
  type ResolvedTheme,
  resolveTheme,
  THEME_STORAGE_KEY,
  type ThemePreference,
  watchSystemTheme,
} from './theme'

interface ThemeContextValue {
  /** What the student chose: reading, light, dark or system. */
  preference: ThemePreference
  /** What is painted right now: reading, light or dark. For `system` this follows the clock. */
  resolved: ResolvedTheme
  setPreference: (next: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

const listeners = new Set<() => void>()
/** Used only when localStorage is blocked (private mode, strict settings): the choice lasts for this page view. */
let memoryPreference: ThemePreference | null = null

function readPreference(): ThemePreference {
  try {
    return parseThemePreference(localStorage.getItem(THEME_STORAGE_KEY))
  } catch {
    return memoryPreference ?? DEFAULT_THEME_PREFERENCE
  }
}

function subscribe(callback: () => void) {
  listeners.add(callback)
  window.addEventListener('storage', callback) // other tabs
  return () => {
    listeners.delete(callback)
    window.removeEventListener('storage', callback)
  }
}

/**
 * Owns theme state. The inline script from `buildThemeInitScript()` has already painted the right theme before React
 * hydrates; this provider keeps it in sync after that (changes, other tabs, the 6 am / 6 pm switch).
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const preference = useSyncExternalStore(subscribe, readPreference, () => DEFAULT_THEME_PREFERENCE)
  const [resolved, setResolved] = useState<ResolvedTheme>(() => resolveTheme(DEFAULT_THEME_PREFERENCE))

  useEffect(() => {
    const apply = (next: ResolvedTheme) => {
      setResolved(next)
      applyResolvedTheme(document.documentElement, next)
    }
    if (preference === 'system') return watchSystemTheme(apply)
    apply(resolveTheme(preference))
  }, [preference])

  const setPreference = useCallback((next: ThemePreference) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      memoryPreference = next
    }
    listeners.forEach((l) => l())
  }, [])

  const value = useMemo(() => ({ preference, resolved, setPreference }), [preference, resolved, setPreference])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
