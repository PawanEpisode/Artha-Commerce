/** One hold never lasts longer than this (FR-K6): a forgotten timer must not keep a screen on all night. */
export const HOLD_CAP_MS = 4 * 60 * 60 * 1000

/**
 * What the status chip says (FR-K4).
 * `held`: the lock is on. `sleep`: wanted but not held (refused, released by the browser, hidden tab or capped).
 * `checking`: the first request is in flight. `off`: nothing asks for it. `unsupported`: the browser has no API.
 */
export type KeepAwakeStatus = 'held' | 'sleep' | 'checking' | 'off' | 'unsupported'

/** The two switches the student sets in Focus settings; they follow the account, not the device (FR-K5). */
export interface KeepAwakeSettings {
  keep_awake: boolean
  keep_awake_in_breaks: boolean
}

/** What a timer is doing right now, in the only terms the lock cares about. */
export interface KeepAwakeActivity {
  /** The clock is counting. A pause, an "away" state and an idle prompt are all not running. */
  running: boolean
  /** A focus round or a stopwatch (true), or a break (false). */
  focus: boolean
}

export const isWakeLockSupported = (): boolean => typeof navigator !== 'undefined' && 'wakeLock' in navigator

/**
 * Whether a timer should hold the screen right now (FR-K1, FR-K2): only while it runs, only for focus unless the
 * student also wants breaks, and only when the switch is on. The same rule for the Pomodoro and the stopwatch.
 */
export function wantsWakeLock(activity: KeepAwakeActivity | null, settings: KeepAwakeSettings | undefined): boolean {
  if (!activity || !settings || !settings.keep_awake) return false
  if (!activity.running) return false
  return activity.focus || settings.keep_awake_in_breaks
}

/** The chip's words, or null when the chip is not shown. Never colour alone: the icon and the text both change. */
export function keepAwakeLabel(status: KeepAwakeStatus): string | null {
  if (status === 'held') return 'Screen stays on'
  if (status === 'sleep') return 'Screen may sleep'
  return null
}
