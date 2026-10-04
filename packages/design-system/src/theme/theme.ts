/**
 * Theme model: pure logic, no React. Shared by the provider, the switcher and the inline no-flash script.
 *
 * Preferences (what the student chooses and what is stored):  reading | light | dark | system
 * Resolved themes (what is painted):                           reading | light | dark
 *
 * "system" is stored as the value `system`. At runtime it behaves as light between 6 am and 6 pm (device local time)
 * and as dark between 6 pm and 6 am, switching on its own while the page stays open.
 */
export const THEME_PREFERENCES = ['reading', 'light', 'dark', 'system'] as const
export type ThemePreference = (typeof THEME_PREFERENCES)[number]
export type ResolvedTheme = Exclude<ThemePreference, 'system'>

/** Reading mode is the default for new visitors. */
export const DEFAULT_THEME_PREFERENCE: ThemePreference = 'reading'
export const THEME_STORAGE_KEY = 'theme'

/** System theme schedule, device local time. Light from 06:00 until 18:00, dark from 18:00 until 06:00. */
export const SYSTEM_LIGHT_START_HOUR = 6
export const SYSTEM_DARK_START_HOUR = 18

/**
 * Browser chrome colour per resolved theme (meta theme-color). Mirrors `--background` in styles.css;
 * `pnpm --filter @artha/design-system check:contrast` prints the exact values to keep in sync.
 */
export const THEME_META_COLORS: Record<ResolvedTheme, string> = {
  reading: '#f7f0dd',
  light: '#fbfaf7',
  dark: '#090d18',
}

export function isThemePreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (THEME_PREFERENCES as readonly string[]).includes(value)
}

/** Unknown, missing or corrupted stored values fall back to the default (Reading). */
export function parseThemePreference(raw: string | null | undefined): ThemePreference {
  return isThemePreference(raw) ? raw : DEFAULT_THEME_PREFERENCE
}

export function isDaytime(now: Date): boolean {
  const hour = now.getHours()
  return hour >= SYSTEM_LIGHT_START_HOUR && hour < SYSTEM_DARK_START_HOUR
}

export function resolveTheme(preference: ThemePreference, now: Date = new Date()): ResolvedTheme {
  if (preference === 'system') return isDaytime(now) ? 'light' : 'dark'
  return preference
}

/** Milliseconds until the next 06:00 or 18:00 (local time). Always greater than zero. */
export function msUntilNextSystemSwitch(now: Date = new Date()): number {
  const next = new Date(now)
  const hour = now.getHours()
  if (hour < SYSTEM_LIGHT_START_HOUR) {
    next.setHours(SYSTEM_LIGHT_START_HOUR, 0, 0, 0)
  } else if (hour < SYSTEM_DARK_START_HOUR) {
    next.setHours(SYSTEM_DARK_START_HOUR, 0, 0, 0)
  } else {
    next.setDate(next.getDate() + 1)
    next.setHours(SYSTEM_LIGHT_START_HOUR, 0, 0, 0)
  }
  return Math.max(1000, next.getTime() - now.getTime())
}

/** Writes the resolved theme to <html>: data-theme, the .dark class and color-scheme (native controls, scrollbars). */
export function applyResolvedTheme(root: HTMLElement, resolved: ResolvedTheme): void {
  root.setAttribute('data-theme', resolved)
  root.classList.toggle('dark', resolved === 'dark')
  root.style.colorScheme = resolved === 'dark' ? 'dark' : 'light'
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_META_COLORS[resolved])
}

/**
 * While the preference is `system`, re-resolves at each 06:00 / 18:00 boundary and whenever the tab becomes visible
 * again (timers are throttled while a laptop sleeps). Returns a cleanup function.
 */
export function watchSystemTheme(onChange: (resolved: ResolvedTheme) => void): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined
  const run = () => {
    clearTimeout(timer)
    onChange(resolveTheme('system'))
    timer = setTimeout(run, msUntilNextSystemSwitch())
  }
  const onVisible = () => {
    if (document.visibilityState === 'visible') run()
  }
  run()
  document.addEventListener('visibilitychange', onVisible)
  return () => {
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', onVisible)
  }
}

/**
 * Inline script for <head>. Runs before first paint so the page never flashes the wrong theme.
 * Keep its logic identical to parseThemePreference + resolveTheme (a unit test runs both and compares).
 */
export function buildThemeInitScript(): string {
  const colors = JSON.stringify(THEME_META_COLORS)
  return `(function(){try{var d=document.documentElement,p=null;try{p=localStorage.getItem(${JSON.stringify(
    THEME_STORAGE_KEY,
  )})}catch(e){}if(p!=='reading'&&p!=='light'&&p!=='dark'&&p!=='system')p=${JSON.stringify(
    DEFAULT_THEME_PREFERENCE,
  )};var r=p;if(p==='system'){var h=new Date().getHours();r=h>=${SYSTEM_LIGHT_START_HOUR}&&h<${SYSTEM_DARK_START_HOUR}?'light':'dark'}d.setAttribute('data-theme',r);d.classList.toggle('dark',r==='dark');d.style.colorScheme=r==='dark'?'dark':'light';var m=document.querySelector('meta[name="theme-color"]');if(m)m.setAttribute('content',${colors}[r])}catch(e){}})();`
}
