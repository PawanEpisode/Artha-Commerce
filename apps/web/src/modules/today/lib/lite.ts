/** Lite mode (FR-F13-40): no motion, no mini charts, a smaller header and a smaller plan payload. Pure. */
import type { TodaySettings } from './types'

export interface NetworkHints {
  saveData?: boolean
  effectiveType?: string
}

/** The browser's connection hints, when it has any (Chrome and Android browsers do; Safari does not). */
export function networkHints(): NetworkHints {
  if (typeof navigator === 'undefined') return {}
  const connection = (navigator as unknown as { connection?: NetworkHints }).connection
  return { saveData: connection?.saveData, effectiveType: connection?.effectiveType }
}

/** `auto` follows the network: Data Saver on, or a connection reported as 2g or slow-2g. `on` and `off` are the student's choice. */
export function isLite(setting: TodaySettings['lite_mode'] | undefined, hints: NetworkHints): boolean {
  if (setting === 'on') return true
  if (setting === 'off') return false
  return hints.saveData === true || hints.effectiveType === '2g' || hints.effectiveType === 'slow-2g'
}
