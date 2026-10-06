import type { SelectOption } from '@artha/design-system'

/** Old names a browser may still report for a zone the API (and the IANA database) calls something else. */
const ALIASES: Readonly<Record<string, string>> = {
  'Asia/Calcutta': 'Asia/Kolkata',
  'Asia/Katmandu': 'Asia/Kathmandu',
  'Asia/Saigon': 'Asia/Ho_Chi_Minh',
  'Asia/Rangoon': 'Asia/Yangon',
}

/** A short list for browsers that cannot enumerate zones: the student's likely ones, India first. */
const FALLBACK_ZONES = [
  'Asia/Kolkata',
  'Asia/Dubai',
  'Asia/Kathmandu',
  'Asia/Dhaka',
  'Asia/Colombo',
  'Asia/Singapore',
  'Asia/Riyadh',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'Australia/Sydney',
  'UTC',
]

export const normalizeTimeZone = (zone: string): string => ALIASES[zone] ?? zone

export function isValidTimeZone(zone: string): boolean {
  try {
    new Intl.DateTimeFormat('en', { timeZone: zone })
    return true
  } catch {
    return false
  }
}

/** The time zone the browser reports, normalised, or null when it reports nothing usable. */
export function browserTimeZone(): string | null {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
    return zone && isValidTimeZone(zone) ? normalizeTimeZone(zone) : null
  } catch {
    return null
  }
}

/** The browser's zone when it differs from the saved one (after alias normalisation), else null: nothing to propose. */
export function proposeTimeZone(saved: string, browser: string | null): string | null {
  if (!browser) return null
  return normalizeTimeZone(saved) === normalizeTimeZone(browser) ? null : browser
}

const readable = (zone: string) => zone.replace(/_/g, ' ').replace(/\//g, ' / ')

/** Select options: every zone the browser knows, always including the saved and the browser's own. */
export function timeZoneOptions(current: string, browser: string | null = browserTimeZone()): SelectOption[] {
  let zones: string[]
  try {
    zones =
      (Intl as typeof Intl & { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ??
      FALLBACK_ZONES
  } catch {
    zones = FALLBACK_ZONES
  }
  const all = new Set(zones.map(normalizeTimeZone))
  all.add(normalizeTimeZone(current))
  if (browser) all.add(browser)
  all.add('UTC')
  return [...all].sort((a, b) => a.localeCompare(b)).map((zone) => ({ value: zone, label: readable(zone) }))
}
