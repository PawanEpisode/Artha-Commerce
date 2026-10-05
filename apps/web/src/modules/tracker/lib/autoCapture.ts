import { AUTO_MAX_CHUNK_SECONDS, MIN_SESSION_SECONDS } from './limits'

export interface Chunk {
  started_at: string
  seconds: number
}

/** Post a chunk once this much active time has gathered (5 minutes), so little is lost if the tab closes. */
export const AUTO_FLUSH_SECONDS = 300
/** A pause in activity longer than this starts a new chunk instead of stretching the old one over the gap. */
export const AUTO_GAP_MS = 5 * 60_000

/**
 * Gathers the seconds a student is actually active on a chapter page (visible tab, recent pointer or key use) into
 * chunks for `POST /tracking/auto/`. Pure and clock-free: the caller passes the time, so it is easy to test.
 */
export function createAccumulator() {
  let seconds = 0
  let startedMs: number | null = null
  let lastActiveMs: number | null = null

  const take = (): Chunk | null => {
    const out =
      startedMs !== null && seconds >= MIN_SESSION_SECONDS
        ? { started_at: new Date(startedMs).toISOString(), seconds: Math.min(seconds, AUTO_MAX_CHUNK_SECONDS) }
        : null
    seconds = 0
    startedMs = null
    return out
  }

  return {
    /** Call once a second. Returns a finished chunk to post, or null. */
    tick(nowMs: number, active: boolean): Chunk | null {
      if (!active) return null
      let done: Chunk | null = null
      if (lastActiveMs !== null && nowMs - lastActiveMs > AUTO_GAP_MS) done = take()
      if (startedMs === null) startedMs = nowMs - 1000
      seconds += 1
      lastActiveMs = nowMs
      return done ?? (seconds >= AUTO_FLUSH_SECONDS ? take() : null)
    },
    /** The tab hides or the page closes: hand over what is gathered, if it is at least a minute. */
    flush(): Chunk | null {
      return take()
    },
    pending: () => seconds,
  }
}
