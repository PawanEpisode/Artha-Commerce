import type { PopOutSize } from './types'

/**
 * The fallback timer window (X-01 W4.4): where Document Picture-in-Picture does not exist (Safari, Firefox below 151)
 * the timer opens in a small separate page. It is its own page, not a portal, so it survives the tab that opened it.
 * It does not stay on top of other windows, and the page says so.
 */
export const MINI_PATH = '/app/focus/mini'
/** A named window, so a second click finds the first one instead of opening another. */
export const MINI_WINDOW_NAME = 'artha-timer'
export const MINI_WINDOW_FEATURES = 'popup,width=320,height=220'

/** Narrower than this the window shows the pill, wider the card (if it is also tall enough for the ring). */
const CARD_MIN_WIDTH = 300
const CARD_MIN_HEIGHT = 260

/** The layout for a window of this inner size: the pill unless there is room for the card. */
export const miniLayout = (width: number, height: number): PopOutSize =>
  width >= CARD_MIN_WIDTH && height >= CARD_MIN_HEIGHT ? 'card' : 'pill'

/**
 * Opens the window, or brings the one that is already open to the front. Call it first thing in a click handler: the
 * browser blocks pop-ups that do not come from a click. Null when the browser blocked it.
 */
export function openMiniWindow(): Window | null {
  if (typeof window === 'undefined') return null
  const win = window.open(MINI_PATH, MINI_WINDOW_NAME, MINI_WINDOW_FEATURES)
  try {
    win?.focus()
  } catch {
    // Some browsers refuse to focus another window; it is open all the same.
  }
  return win
}

const NOTE_KEY = 'artha:mini-note-seen'

/** The one-time note, remembered on this device (a convenience, so storage that throws just shows it again). */
export function miniNoteSeen(storage: Pick<Storage, 'getItem'> | null = safeStorage()): boolean {
  try {
    return storage?.getItem(NOTE_KEY) === '1'
  } catch {
    return false
  }
}

export function markMiniNoteSeen(storage: Pick<Storage, 'setItem'> | null = safeStorage()): void {
  try {
    storage?.setItem(NOTE_KEY, '1')
  } catch {
    // Not remembered: the note may show again, which is harmless.
  }
}

function safeStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}
