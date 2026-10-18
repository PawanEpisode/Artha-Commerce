/**
 * The practice session clock as a pure function of what the server said, so the docked timer, the player and the tests
 * agree. Timed sessions count down to `deadline_at`; untimed ones count up from `started_at`; both stand still while
 * the session is paused and both read the server's time (through `server_now`), never trusting the device clock.
 */

export interface ClockSource {
  status: string
  time_limit_seconds: number | null
  started_at: string | null
  deadline_at: string | null
  paused_at: string | null
  paused_total_seconds: number
  /** The server's time when this was sent. */
  server_now: string
  /** `Date.now()` on this device when it arrived. */
  receivedAtMs: number
}

export type PracticeClock =
  | { kind: 'waiting' }
  | { kind: 'countdown'; seconds: number; paused: boolean; expired: boolean }
  | { kind: 'elapsed'; seconds: number; paused: boolean; expired: false }

const RUNNING = new Set(['in_progress', 'paused'])

const parse = (iso: string | null): number | null => {
  if (!iso) return null
  const ms = Date.parse(iso)
  return Number.isNaN(ms) ? null : ms
}

/** How far this device's clock is ahead of the server's (negative: behind), as of when the data arrived. */
export function clockOffsetMs(source: Pick<ClockSource, 'server_now' | 'receivedAtMs'>): number {
  const server = parse(source.server_now)
  return server === null ? 0 : source.receivedAtMs - server
}

export function practiceClock(source: ClockSource, deviceNowMs: number): PracticeClock {
  const startedMs = parse(source.started_at)
  if (!RUNNING.has(source.status) || startedMs === null) return { kind: 'waiting' }

  const paused = source.status === 'paused'
  const serverNowMs = deviceNowMs - clockOffsetMs(source)
  // A paused clock is frozen at the moment it was paused.
  const reference = paused ? (parse(source.paused_at) ?? serverNowMs) : serverNowMs

  if (source.time_limit_seconds !== null) {
    const deadlineMs =
      parse(source.deadline_at) ?? startedMs + (source.time_limit_seconds + source.paused_total_seconds) * 1000
    const seconds = Math.max(0, Math.ceil((deadlineMs - reference) / 1000))
    return { kind: 'countdown', seconds, paused, expired: !paused && seconds === 0 }
  }

  const seconds = Math.max(0, Math.floor((reference - startedMs) / 1000) - source.paused_total_seconds)
  return { kind: 'elapsed', seconds, paused, expired: false }
}

/** Seconds left at which a countdown speaks up, smallest first (a long gap is announced by its lowest mark). */
export const COUNTDOWN_WARNINGS = [60, 300, 600] as const

/**
 * What a screen reader should hear when a countdown moves from `previous` to `current` seconds, or null. Only the
 * moments that matter are spoken, never every tick. A `previous` of null (first sight) says nothing.
 */
export function countdownAnnouncement(previous: number | null, current: number): string | null {
  if (previous === null || current >= previous) return null
  if (current === 0) return 'Time is up.'
  for (const mark of COUNTDOWN_WARNINGS) {
    if (previous > mark && current <= mark) return `${mark / 60} ${mark === 60 ? 'minute' : 'minutes'} left.`
  }
  return null
}
