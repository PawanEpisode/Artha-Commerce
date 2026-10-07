import { EXTEND_SECONDS, MAX_EXTENSIONS } from './presets'
import type { FocusTimer, IdleInfo, Phase } from './types'

/**
 * The countdown is never counted: it is derived from the phase's start, its pause total and the clock, exactly as the
 * server derives it. A reload, a sleeping tab or a second device therefore all show the same number. Pure.
 */
type Clocked = Pick<FocusTimer, 'started_at' | 'paused_at' | 'paused_total_seconds'>

export function elapsedSeconds(t: Clocked, nowMs: number): number {
  const end = t.paused_at ? Math.min(nowMs, Date.parse(t.paused_at)) : nowMs
  return Math.max(0, Math.floor((end - Date.parse(t.started_at)) / 1000) - t.paused_total_seconds)
}

export function remainingSeconds(t: Clocked & Pick<FocusTimer, 'planned_seconds'>, nowMs: number): number {
  return Math.max(0, t.planned_seconds - elapsedSeconds(t, nowMs))
}

/**
 * Extra focus time: how far a round has run past its planned length, or null when it has not (or cannot: breaks,
 * rounds started with overtime off). Derived from the clock like everything else, so it matches the server.
 */
export function overtimeOf(
  t: Clocked & Pick<FocusTimer, 'planned_seconds' | 'phase' | 'status' | 'overtime_enabled'>,
  nowMs: number,
): number | null {
  if (t.phase !== 'focus' || !t.overtime_enabled || t.status === 'away') return null
  const extra = elapsedSeconds(t, nowMs) - t.planned_seconds
  return extra >= 0 ? extra : null
}

/** True once a running phase has reached zero. A paused phase never finishes by itself. */
export function isFinished(t: Clocked & Pick<FocusTimer, 'planned_seconds' | 'status'>, nowMs: number): boolean {
  return t.status === 'running' && remainingSeconds(t, nowMs) === 0
}

export function percentDone(t: Clocked & Pick<FocusTimer, 'planned_seconds'>, nowMs: number): number {
  return t.planned_seconds > 0 ? Math.min(100, (elapsedSeconds(t, nowMs) / t.planned_seconds) * 100) : 0
}

/** `+12:03`: extra focus time after the planned length. */
export const formatOvertime = (seconds: number) => `+${formatRemaining(seconds)}`

/** 24:12 under an hour, 1:05:00 from one hour on. */
export function formatRemaining(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`
}

/** "24 minutes 12 seconds": whole words, so a screen reader never says "min" or "s". */
export function spokenRemaining(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const m = Math.floor(s / 60)
  const rest = s % 60
  const unit = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
  if (m === 0) return unit(rest, 'second')
  return rest === 0 ? unit(m, 'minute') : `${unit(m, 'minute')} ${unit(rest, 'second')}`
}

export const PHASE_LABEL: Record<Phase, string> = {
  focus: 'Focus',
  short_break: 'Short break',
  long_break: 'Long break',
}

/** Browser tab title: the countdown first, so it reads in a narrow tab ("24:12 Focus"). */
export function tabTitle(t: FocusTimer | null, nowMs: number, base: string): string {
  if (!t) return base
  if (t.status === 'away') return `Did you finish? · ${base}`
  const extra = overtimeOf(t, nowMs)
  const clock = extra === null ? formatRemaining(remainingSeconds(t, nowMs)) : formatOvertime(extra)
  const label = t.phase === 'focus' ? 'Focus' : 'Break'
  return t.status === 'paused' ? `Paused ${clock}` : `${clock} ${label}`
}

/** The label of the Start button: it continues a remembered cycle instead of restarting it. */
export function startLabel(idle: IdleInfo | null): string {
  if (!idle) return 'Start'
  if (idle.next_phase === 'focus')
    return idle.next_round === 1 ? 'Start' : `Start round ${idle.next_round} of ${idle.rounds_before_long}`
  return idle.next_phase === 'long_break' ? 'Start long break' : 'Start short break'
}

// --- The timer as the page shows it while an action waits in the offline queue ---------------------------------
export function localPause(t: FocusTimer, atIso: string): FocusTimer {
  if (t.paused_at || t.phase !== 'focus') return t
  return { ...t, status: 'paused', paused_at: atIso, pause_count: t.pause_count + 1, ends_at: null }
}

export function localResume(t: FocusTimer, atIso: string): FocusTimer {
  if (!t.paused_at) return t
  const pausedFor = Math.max(0, Math.floor((Date.parse(atIso) - Date.parse(t.paused_at)) / 1000))
  const paused_total_seconds = t.paused_total_seconds + pausedFor
  return {
    ...t,
    status: 'running',
    paused_at: null,
    paused_total_seconds,
    ends_at: new Date(Date.parse(t.started_at) + (t.planned_seconds + paused_total_seconds) * 1000).toISOString(),
  }
}

export function localExtend(t: FocusTimer): FocusTimer {
  if (t.phase !== 'focus' || t.extension_count >= MAX_EXTENSIONS) return t
  const planned_seconds = t.planned_seconds + EXTEND_SECONDS
  const extension_count = t.extension_count + 1
  return {
    ...t,
    planned_seconds,
    extension_count,
    can_extend: extension_count < MAX_EXTENSIONS,
    ends_at: t.paused_at
      ? null
      : new Date(Date.parse(t.started_at) + (planned_seconds + t.paused_total_seconds) * 1000).toISOString(),
  }
}

// --- How long a student takes to act once a phase has ended (X-01 PRD B, `phase_end_acknowledged`) ---------------
/** A gap longer than this is reported as this: the student was simply away. */
export const MAX_ACK_GAP_SECONDS = 7200

/** A phase that ended and has not been acted on yet. */
export interface PendingEnd {
  clientId: string
  phase: Phase
  /** When the phase reached zero, in epoch milliseconds on the server's clock. */
  at: number
}

/** When a phase that is not paused reaches zero (the web twin of `timing.phase_end_at`). */
export function phaseEndMs(t: Pick<FocusTimer, 'started_at' | 'planned_seconds' | 'paused_total_seconds'>): number {
  return Date.parse(t.started_at) + (t.planned_seconds + t.paused_total_seconds) * 1000
}

/**
 * Keeps track of the phase end the student has yet to answer. A timer that has reached its end (or is "away") becomes
 * the pending end; a different timer that is still running drops it; idle (no timer) keeps it, because the next Start
 * is exactly the action being timed.
 */
export function nextPendingEnd(pending: PendingEnd | null, t: FocusTimer | null, nowMs: number): PendingEnd | null {
  if (!t) return pending
  if (pending?.clientId === t.client_id) return pending
  if (t.status === 'away' || isFinished(t, nowMs)) return { clientId: t.client_id, phase: t.phase, at: phaseEndMs(t) }
  return null
}

/** Whole seconds from the end of a phase to the student's action, capped; null when the action came first. */
export function phaseEndGap(endAtMs: number, actionAtMs: number): number | null {
  const seconds = Math.floor((actionAtMs - endAtMs) / 1000)
  return seconds < 0 ? null : Math.min(seconds, MAX_ACK_GAP_SECONDS)
}
