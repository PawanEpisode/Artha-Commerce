import { elapsedSeconds } from './duration'
import type { ActivityType, Stopwatch } from './types'

/**
 * The stopwatch as the page shows it while an action is waiting in the offline queue. The server replays the same
 * action with the same moment (`at`), so the two agree once the queue is flushed. Pure.
 */
export function localStart(
  nowIso: string,
  clientId: string,
  context: { subject_id: string | null; chapter_id: string | null; activity_type: ActivityType },
): Stopwatch {
  return {
    status: 'running',
    started_at: nowIso,
    paused_at: null,
    paused_total_seconds: 0,
    pause_count: 0,
    elapsed_seconds: 0,
    last_seen_at: nowIso,
    last_active_at: nowIso,
    idle_pending: false,
    idle_prompted_at: null,
    idle_due: false,
    client_id: clientId,
    version: 1,
    ...context,
  }
}

export function localPause(sw: Stopwatch, nowIso: string): Stopwatch {
  if (sw.status === 'paused') return sw
  return {
    ...sw,
    status: 'paused',
    paused_at: nowIso,
    pause_count: sw.pause_count + 1,
    elapsed_seconds: elapsedSeconds(sw, Date.parse(nowIso)),
  }
}

export function localResume(sw: Stopwatch, nowIso: string): Stopwatch {
  if (sw.status === 'running' || !sw.paused_at) return sw
  const paused = Math.max(0, Math.floor((Date.parse(nowIso) - Date.parse(sw.paused_at)) / 1000))
  return {
    ...sw,
    status: 'running',
    paused_at: null,
    paused_total_seconds: sw.paused_total_seconds + paused,
    last_active_at: nowIso,
  }
}
