import type { Environment } from './platform'

/**
 * The install offer (X-01 W4.5, FR-C7). Installing is per device, so what counts is kept per device: how many focus
 * rounds were finished here and when the offer was last shown. Everything in this file is pure.
 */

/** Finished focus rounds on this device before the offer may appear (the student has seen the timer work). */
export const INSTALL_AFTER_ROUNDS = 2
export const INSTALL_COOLDOWN_DAYS = 30
const DAY_MS = 24 * 60 * 60 * 1000

/**
 * How this browser can install Artha, or null where it cannot or must not be offered:
 * - `prompt`: Chrome and Edge fired `beforeinstallprompt`, so one button installs it.
 * - `ios_steps`: iPhone or iPad Safari, which only has Share, then Add to Home Screen.
 * - `mac_safari`: Safari on a Mac (File, then Add to Dock).
 * Never inside the installed app, never inside another app's browser, never where the browser has no install.
 */
export type InstallKind = 'prompt' | 'ios_steps' | 'mac_safari'

export function installKind(
  env: Pick<Environment, 'platform' | 'browser' | 'displayMode' | 'inAppBrowser'>,
  canPrompt: boolean,
): InstallKind | null {
  if (env.displayMode === 'standalone' || env.inAppBrowser) return null
  if (env.platform === 'ios') return env.browser === 'safari' ? 'ios_steps' : null
  if (canPrompt) return 'prompt'
  if (env.platform === 'macos' && env.browser === 'safari') return 'mac_safari'
  return null
}

export interface InstallOfferFacts {
  /** The `floating_timer` flag (fails open). At 0% the offer disappears with the rest of P4. */
  flagOn: boolean
  kind: InstallKind | null
  /** Focus rounds finished on this device, ever. */
  deviceRounds: number
  /** Focus rounds that ended during this visit: the offer waits for the moment a round has just finished. */
  roundsFinished: number
  /** When the offer was last shown on this device (epoch ms), or null. */
  lastOfferedAt: number | null
  now: number
}

export const installOfferDue = (f: InstallOfferFacts): boolean =>
  f.flagOn &&
  f.kind !== null &&
  f.roundsFinished > 0 &&
  f.deviceRounds >= INSTALL_AFTER_ROUNDS &&
  (f.lastOfferedAt === null || f.now - f.lastOfferedAt >= INSTALL_COOLDOWN_DAYS * DAY_MS)
