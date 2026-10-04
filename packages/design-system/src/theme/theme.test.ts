import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildThemeInitScript,
  DEFAULT_THEME_PREFERENCE,
  isDaytime,
  msUntilNextSystemSwitch,
  parseThemePreference,
  resolveTheme,
  THEME_META_COLORS,
  THEME_PREFERENCES,
  type ThemePreference,
  watchSystemTheme,
} from './theme'

const at = (h: number, m = 0, s = 0) => new Date(2026, 9, 4, h, m, s) // 4 Oct 2026, local time

describe('defaults and parsing', () => {
  it('defaults to Reading mode', () => {
    expect(DEFAULT_THEME_PREFERENCE).toBe('reading')
  })
  it('accepts every known preference including legacy light and dark', () => {
    for (const p of THEME_PREFERENCES) expect(parseThemePreference(p)).toBe(p)
  })
  it('falls back to Reading for missing or corrupted values', () => {
    for (const bad of [null, undefined, '', 'sepia', 'DARK', '{"x":1}']) {
      expect(parseThemePreference(bad)).toBe('reading')
    }
  })
})

describe('system theme by time of day', () => {
  it('is light from 06:00 until 17:59', () => {
    expect(resolveTheme('system', at(6, 0))).toBe('light')
    expect(resolveTheme('system', at(12, 30))).toBe('light')
    expect(resolveTheme('system', at(17, 59, 59))).toBe('light')
  })
  it('is dark from 18:00 until 05:59', () => {
    expect(resolveTheme('system', at(18, 0))).toBe('dark')
    expect(resolveTheme('system', at(23, 59))).toBe('dark')
    expect(resolveTheme('system', at(0, 0))).toBe('dark')
    expect(resolveTheme('system', at(5, 59, 59))).toBe('dark')
  })
  it('leaves explicit themes untouched at any hour', () => {
    for (const p of ['reading', 'light', 'dark'] as const) {
      expect(resolveTheme(p, at(3))).toBe(p)
      expect(resolveTheme(p, at(15))).toBe(p)
    }
  })
  it('isDaytime matches the boundaries', () => {
    expect(isDaytime(at(5, 59))).toBe(false)
    expect(isDaytime(at(6, 0))).toBe(true)
    expect(isDaytime(at(17, 59))).toBe(true)
    expect(isDaytime(at(18, 0))).toBe(false)
  })
})

describe('msUntilNextSystemSwitch', () => {
  const hours = (ms: number) => ms / 3_600_000
  it('before 06:00 waits for 06:00 the same day', () => {
    expect(hours(msUntilNextSystemSwitch(at(4, 0)))).toBeCloseTo(2)
  })
  it('during the day waits for 18:00', () => {
    expect(hours(msUntilNextSystemSwitch(at(9, 0)))).toBeCloseTo(9)
  })
  it('after 18:00 waits for 06:00 the next day', () => {
    expect(hours(msUntilNextSystemSwitch(at(20, 0)))).toBeCloseTo(10)
    expect(hours(msUntilNextSystemSwitch(at(23, 30)))).toBeCloseTo(6.5)
  })
  it('at exactly a boundary waits for the following one, never zero', () => {
    expect(hours(msUntilNextSystemSwitch(at(6, 0)))).toBeCloseTo(12)
    expect(hours(msUntilNextSystemSwitch(at(18, 0)))).toBeCloseTo(12)
  })
})

describe('watchSystemTheme', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('switches from light to dark when the clock crosses 18:00 while the page is open', () => {
    vi.useFakeTimers()
    vi.setSystemTime(at(17, 59, 30))
    const doc = { visibilityState: 'visible', addEventListener: vi.fn(), removeEventListener: vi.fn() }
    vi.stubGlobal('document', doc)
    const seen: string[] = []
    const stop = watchSystemTheme((r) => seen.push(r))
    expect(seen).toEqual(['light'])
    vi.advanceTimersByTime(31_000)
    expect(seen).toEqual(['light', 'dark'])
    stop()
    vi.advanceTimersByTime(24 * 3_600_000)
    expect(seen).toEqual(['light', 'dark'])
    expect(doc.removeEventListener).toHaveBeenCalled()
  })
})

describe('inline no-flash script', () => {
  /** Runs the generated script against a minimal fake DOM and returns what it painted. */
  function run(stored: string | null, now: Date) {
    const attrs: Record<string, string> = {}
    const classes = new Set<string>()
    const meta = { setAttribute: vi.fn() }
    const root = {
      setAttribute: (k: string, v: string) => (attrs[k] = v),
      classList: { toggle: (c: string, on: boolean) => (on ? classes.add(c) : classes.delete(c)) },
      style: {} as Record<string, string>,
    }
    const RealDate = Date
    class FakeDate extends RealDate {
      constructor() {
        super(now.getTime())
      }
    }
    new Function('document', 'localStorage', 'Date', buildThemeInitScript())(
      { documentElement: root, querySelector: () => meta },
      { getItem: () => stored },
      FakeDate,
    )
    return { theme: attrs['data-theme'], dark: classes.has('dark'), scheme: root.style.colorScheme, meta }
  }

  it('paints Reading when nothing is stored', () => {
    const r = run(null, at(14))
    expect(r).toMatchObject({ theme: 'reading', dark: false, scheme: 'light' })
    expect(r.meta.setAttribute).toHaveBeenCalledWith('content', THEME_META_COLORS.reading)
  })
  it('paints Reading for corrupted values', () => {
    expect(run('rainbow', at(14)).theme).toBe('reading')
  })
  it('agrees with resolveTheme for every preference at every hour', () => {
    for (const pref of THEME_PREFERENCES as readonly ThemePreference[]) {
      for (let h = 0; h < 24; h++) {
        const painted = run(pref, at(h, 15))
        const expected = resolveTheme(pref, at(h, 15))
        expect(painted.theme).toBe(expected)
        expect(painted.dark).toBe(expected === 'dark')
      }
    }
  })
  it('survives blocked storage', () => {
    const attrs: Record<string, string> = {}
    new Function('document', 'localStorage', buildThemeInitScript())(
      {
        documentElement: {
          setAttribute: (k: string, v: string) => (attrs[k] = v),
          classList: { toggle() {} },
          style: {},
        },
        querySelector: () => null,
      },
      {
        getItem: () => {
          throw new Error('blocked')
        },
      },
    )
    expect(attrs['data-theme']).toBe('reading')
  })
})
