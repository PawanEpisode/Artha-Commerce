import { type ActivityType, formatClock, spokenDuration } from '~/modules/tracker'

import { EXTEND_SECONDS, MAX_EXTENSIONS } from './presets'
import {
  formatOvertime,
  formatRemaining,
  overtimeOf,
  percentDone,
  PHASE_LABEL,
  phaseEndMs,
  remainingSeconds,
  spokenRemaining,
} from './timer-math'
import type { FocusSettings, FocusTimer, IdleInfo, Phase, PopOutSize } from './types'

/**
 * What the floating timer shows and offers in each timer state (X-01 PRD B, "Behaviour per timer state"). Everything
 * here is pure: the corner timer, the pill and the card all draw the same `PopoutView`, and its controls call the same
 * actions as the focus page, so the window has no timer logic of its own.
 */

/** Window sizes in CSS pixels (inner). Chrome opens nothing smaller than about 320 x 156, so the pill is that size. */
export const POPOUT_SIZES: Record<PopOutSize, readonly [width: number, height: number]> = {
  pill: [320, 156],
  card: [320, 300],
}

/** The server's `PRESENCE_WINDOW_SECONDS`, and the window the Android buttons use (`present_by_tap`). */
export const PRESENCE_WINDOW_SECONDS = 120

export type PopoutKind = 'focus' | 'overtime' | 'paused' | 'away' | 'break' | 'waiting' | 'idle' | 'stopwatch'

export type PopoutControlId =
  | 'pause'
  | 'resume'
  | 'extend'
  | 'end'
  | 'stop_save'
  | 'skip_break'
  | 'start_next'
  | 'claim_yes'
  | 'claim_no'
  | 'back'
  | 'save_end'
  | 'discard'
  | 'keep_going'

/** The icon a control wears; the view maps it to the design system's icons. */
export type PopoutIcon = 'pause' | 'play' | 'skip' | 'stop' | 'coffee' | 'back' | 'check' | 'close' | null

export interface PopoutControl {
  id: PopoutControlId
  label: string
  icon: PopoutIcon
  /** The button that leads the next step (drawn solid). */
  primary: boolean
  disabled: boolean
  /** Shown in the pill too; the card shows every control. */
  pill: boolean
  /** Only the icon is drawn; `label` is still its accessible name. */
  iconOnly: boolean
}

export interface PopoutView {
  kind: PopoutKind
  phase: Phase | 'stopwatch' | null
  /** The name of what runs: "Focus round", "Short break", "Stopwatch". */
  label: string
  /** Under the clock: "Round 2 of 4", "Target reached". */
  caption: string
  /** A sentence for states without a ring; the card shows it instead of the ring. */
  message: string | null
  clock: string
  /** "24 minutes 12 seconds left": what a screen reader says for the clock. */
  spoken: string
  percent: number
  /** Past the target, waiting for the student, or away: drawn in the phase-end colour. */
  ended: boolean
  paused: boolean
  /** The card draws the progress ring (false for states that ask a question or wait). */
  ring: boolean
  controls: PopoutControl[]
}

/** Subject, chapter and activity of the round the window last showed, so "Start round N" can continue it. */
export interface PopoutContext {
  subject_id: string | null
  chapter_id: string | null
  activity_type: ActivityType
}

export interface PopoutStopwatch {
  paused: boolean
  seconds: number
}

const control = (
  id: PopoutControlId,
  label: string,
  icon: PopoutIcon,
  o: { primary?: boolean; disabled?: boolean; pill?: boolean; iconOnly?: boolean } = {},
): PopoutControl => ({
  id,
  label,
  icon,
  primary: o.primary ?? false,
  disabled: o.disabled ?? false,
  pill: o.pill ?? false,
  iconOnly: o.iconOnly ?? false,
})

const BACK = control('back', 'Back to Artha', 'back', { primary: true, pill: true })
const roundCaption = (t: FocusTimer) => `Round ${t.round_number} of ${t.rounds_before_long}`

/** The context a timer carries, remembered for the next "Start round N". Returns `previous` itself when nothing changed. */
export function rememberContext(previous: PopoutContext | null, timer: FocusTimer | null): PopoutContext | null {
  if (!timer) return previous
  const { subject_id, chapter_id, activity_type } = timer
  const same =
    previous?.subject_id === subject_id &&
    previous.chapter_id === chapter_id &&
    previous.activity_type === activity_type
  return same ? previous : { subject_id, chapter_id, activity_type }
}

function stopwatchView(sw: PopoutStopwatch): PopoutView {
  return {
    kind: 'stopwatch',
    phase: 'stopwatch',
    label: 'Stopwatch',
    caption: sw.paused ? 'Paused' : 'Elapsed',
    message: null,
    clock: formatClock(sw.seconds),
    spoken: `Elapsed ${spokenDuration(sw.seconds)}`,
    percent: 0,
    ended: false,
    paused: sw.paused,
    ring: false,
    controls: [
      sw.paused
        ? control('resume', 'Resume', 'play', { primary: true, pill: true })
        : control('pause', 'Pause', 'pause', { pill: true }),
    ],
  }
}

function awayView(t: FocusTimer): PopoutView {
  return {
    kind: 'away',
    phase: t.phase,
    label: 'Focus round',
    caption: roundCaption(t),
    message: 'The round ended while you were away. Did you study through it?',
    clock: 'Count it?',
    spoken: 'The round ended while you were away. Count it?',
    percent: 100,
    ended: true,
    paused: false,
    ring: false,
    controls: [
      control('claim_yes', 'Yes', 'check', { primary: true, pill: true }),
      control('claim_no', 'No', 'close', { pill: true }),
    ],
  }
}

function breakView(t: FocusTimer, now: number): PopoutView {
  const left = remainingSeconds(t, now)
  return {
    kind: 'break',
    phase: t.phase,
    label: PHASE_LABEL[t.phase],
    caption: `After round ${t.round_number}`,
    message: null,
    clock: formatRemaining(left),
    spoken: `${spokenRemaining(left)} left`,
    percent: percentDone(t, now),
    ended: false,
    paused: false,
    ring: true,
    controls: [control('skip_break', 'Skip break', 'skip', { pill: true })],
  }
}

function overtimeView(t: FocusTimer, extra: number): PopoutView {
  const paused = t.status === 'paused'
  // With breaks that start by themselves, saving the round starts the break; otherwise it only saves.
  const stop = t.auto_start_breaks
    ? control('stop_save', 'Start break', 'coffee', { primary: !paused, pill: !paused })
    : control('stop_save', 'Stop and save', 'stop', { primary: !paused, pill: !paused })
  return {
    kind: 'overtime',
    phase: t.phase,
    label: 'Focus round',
    caption: paused ? 'Target reached · paused' : 'Target reached',
    message: null,
    clock: formatOvertime(extra),
    spoken: `${spokenRemaining(extra)} of extra focus`,
    percent: 100,
    ended: true,
    paused,
    ring: true,
    // +5 and End are not offered past the target, as on the focus page: the server refuses an extension there.
    controls: paused
      ? [control('resume', 'Resume', 'play', { primary: true, pill: true }), stop]
      : [stop, control('pause', 'Pause', 'pause')],
  }
}

function focusView(t: FocusTimer, now: number): PopoutView {
  const extra = overtimeOf(t, now)
  if (extra !== null) return overtimeView(t, extra)
  const left = remainingSeconds(t, now)
  const paused = t.status === 'paused'
  const extensionsLeft = MAX_EXTENSIONS - t.extension_count
  return {
    kind: paused ? 'paused' : 'focus',
    phase: t.phase,
    label: 'Focus round',
    caption: paused ? `${roundCaption(t)} · paused` : roundCaption(t),
    message: null,
    clock: formatRemaining(left),
    spoken: `${spokenRemaining(left)} left${paused ? ', paused' : ''}`,
    percent: percentDone(t, now),
    ended: false,
    paused,
    ring: true,
    controls: paused
      ? [control('resume', 'Resume', 'play', { primary: true, pill: true }), control('end', 'End', 'stop')]
      : [
          control('pause', 'Pause', 'pause', { pill: true }),
          control('extend', `+${EXTEND_SECONDS / 60}${extensionsLeft > 0 ? ` (${extensionsLeft} left)` : ''}`, null, {
            disabled: !t.can_extend,
          }),
          control('end', 'End', 'stop'),
        ],
  }
}

/** Nothing runs: a phase just closed and the next step waits (a break is due, or the next round), or nothing is due. */
function restingView(idle: IdleInfo | null, last: PopoutContext | null): PopoutView {
  if (!idle || (idle.next_phase === 'focus' && idle.next_round <= 1)) {
    return {
      kind: 'idle',
      phase: null,
      label: 'Timer',
      caption: '',
      message: 'Start a round in Artha when you are ready.',
      clock: 'No timer running',
      spoken: 'No timer running',
      percent: 0,
      ended: false,
      paused: false,
      ring: false,
      controls: [BACK],
    }
  }
  const toBreak = idle.next_phase !== 'focus'
  const next = toBreak
    ? control('start_next', idle.next_phase === 'long_break' ? 'Start long break' : 'Start break', 'coffee', {
        primary: true,
        pill: true,
      })
    : control('start_next', `Start round ${idle.next_round}`, 'play', { primary: true, pill: true })
  return {
    kind: 'waiting',
    phase: idle.next_phase,
    label: toBreak ? 'Focus round' : 'Break',
    caption: toBreak ? 'Your break is waiting' : `Round ${idle.next_round} of ${idle.rounds_before_long} is next`,
    message: toBreak
      ? 'Focus round done. Start your break when you are ready.'
      : 'Break is over. Ready for the next round?',
    clock: toBreak ? 'Round done' : 'Break over',
    spoken: toBreak ? 'Focus round done' : 'Break is over',
    percent: 100,
    ended: true,
    paused: false,
    ring: false,
    // A round needs a subject and a chapter: with none remembered, the only way on is back in Artha.
    controls: last ? [next] : [BACK],
  }
}

/**
 * The view for whichever timer is live: a stopwatch, a round or break, or neither. `last` is the context of the round
 * the window last showed (null when it was opened while nothing ran). Pure.
 */
export function popoutView(
  timer: FocusTimer | null,
  idle: IdleInfo | null,
  stopwatch: PopoutStopwatch | null,
  nowMs: number,
  last: PopoutContext | null,
): PopoutView {
  if (stopwatch) return stopwatchView(stopwatch)
  if (!timer) return restingView(idle, last)
  if (timer.status === 'away') return awayView(timer)
  return timer.phase === 'focus' ? focusView(timer, nowMs) : breakView(timer, nowMs)
}

/** The inline confirm that replaces the controls after End (a round under one minute skips it). */
export const END_CONFIRM_CONTROLS: readonly PopoutControl[] = [
  control('save_end', 'Save and end', 'check', { primary: true, pill: true }),
  control('discard', 'Discard', null, { pill: true }),
  control('keep_going', 'Keep going', 'close', { pill: true, iconOnly: true }),
]

/** The controls shown at this size. `canGoBack` is false where the browser cannot focus the opener tab (S4.6). */
export function visibleControls(controls: readonly PopoutControl[], size: PopOutSize, canGoBack: boolean) {
  return controls.filter((c) => (c.id !== 'back' || canGoBack) && (size === 'card' || c.pill))
}

/** The request that starts the next phase from the window: the fields the focus page sends, with the remembered context. */
export function nextStartBody(idle: IdleInfo, last: PopoutContext, settings: FocusSettings) {
  const rhythm =
    settings.preset === 'custom'
      ? {
          preset: 'custom',
          focus_minutes: settings.focus_minutes,
          short_break_minutes: settings.short_break_minutes,
          long_break_minutes: settings.long_break_minutes,
          rounds_before_long: settings.rounds_before_long,
        }
      : { preset: settings.preset }
  return { ...(idle.next_phase === 'focus' ? rhythm : {}), phase: idle.next_phase, ...last }
}

// --- Presence (PRD B, "Presence while the pop-out is open") --------------------------------------------------------

export interface PopoutPresence {
  /** When the running phase reaches its target (epoch ms, server clock), or null while paused or idle. */
  targetMs: number | null
  /** The first tap in the window after the target and inside the presence window, or null. */
  tapMs: number | null
}

export const phaseTarget = (t: FocusTimer | null): number | null => (t && t.status === 'running' ? phaseEndMs(t) : null)

/** A tap in the window counts only when it falls after the target and inside the presence window. */
export function presenceAfterTap(p: PopoutPresence, nowMs: number): PopoutPresence {
  if (p.targetMs === null || p.tapMs !== null) return p
  const late = nowMs - p.targetMs
  return late >= 0 && late <= PRESENCE_WINDOW_SECONDS * 1000 ? { ...p, tapMs: nowMs } : p
}

export const presenceFlags = (p: PopoutPresence, nowMs: number) => ({
  pastTarget: p.targetMs !== null && nowMs >= p.targetMs,
  tappedSinceTarget: p.tapMs !== null,
})

/**
 * Whether the timer read says `alive=1`. A visible tab with a recent tap or key always does (the rule before P4). An
 * open, visible pop-out does too until the target; from the target on it needs one tap in the window.
 */
export function popoutAlive(i: {
  tabVisible: boolean
  recentlyActive: boolean
  popoutOpen: boolean
  pastTarget: boolean
  tappedSinceTarget: boolean
}): boolean {
  if (i.tabVisible && i.recentlyActive) return true
  return i.popoutOpen && (!i.pastTarget || i.tappedSinceTarget)
}

// --- popout_session analytics: one event per focus round that had the window open --------------------------------

export interface PopoutRound {
  clientId: string
  round: number
  /** Seconds the window was open during this round, up to `since`. */
  seconds: number
  /** When the window was last seen open during the round; null while it is closed. */
  since: number | null
  reachedTarget: boolean
}

export interface PopoutRoundReport {
  round_number: number
  completed: boolean
  seconds_with_popout: number
}

const beginRound = (t: FocusTimer, open: boolean, nowMs: number): PopoutRound => ({
  clientId: t.client_id,
  round: t.round_number,
  seconds: 0,
  since: open ? nowMs : null,
  reachedTarget: remainingSeconds(t, nowMs) === 0,
})

const settleRound = (r: PopoutRound, nowMs: number): PopoutRound => ({
  ...r,
  seconds: r.seconds + (r.since === null ? 0 : Math.max(0, (nowMs - r.since) / 1000)),
  since: null,
})

/**
 * Follows the current focus round and how long the window was open during it. Returns the next state and, when a round
 * that had the window open has just ended, its report. Pure; call it whenever the timer or the window changes.
 */
export function advanceRound(
  prev: PopoutRound | null,
  timer: FocusTimer | null,
  open: boolean,
  nowMs: number,
): { next: PopoutRound | null; report: PopoutRoundReport | null } {
  const round = timer && timer.phase === 'focus' && timer.status !== 'away' ? timer : null
  if (!prev) return { next: round ? beginRound(round, open, nowMs) : null, report: null }
  const settled = settleRound(prev, nowMs)
  if (!round || round.client_id !== prev.clientId) {
    const report =
      settled.seconds >= 1
        ? {
            round_number: settled.round,
            completed: settled.reachedTarget,
            seconds_with_popout: Math.round(settled.seconds),
          }
        : null
    return { next: round ? beginRound(round, open, nowMs) : null, report }
  }
  const reachedTarget = settled.reachedTarget || remainingSeconds(round, nowMs) === 0
  return { next: { ...settled, reachedTarget, since: open ? nowMs : null }, report: null }
}

// --- start-of-round prompt and pop out on Start (X-01 W4.3) -------------------------------------------------------

/**
 * Whether to offer the start-of-round prompt "Keep the timer on top while you study?". Only on a desktop browser that
 * has Document Picture-in-Picture (the fallback window does not stay on top, so it is never offered), with the
 * `floating_timer` flag on, once ever per student (`popoutPromptSeen`), while the setting is still off, during a focus
 * round (not a break) and while no window is open.
 */
export function promptEligible(i: {
  supported: boolean
  desktop: boolean
  flagOn: boolean
  popoutPromptSeen: boolean
  popoutOnStart: boolean
  phase: Phase | null
  popoutOpen: boolean
}): boolean {
  return (
    i.supported &&
    i.desktop &&
    i.flagOn &&
    !i.popoutPromptSeen &&
    !i.popoutOnStart &&
    i.phase === 'focus' &&
    !i.popoutOpen
  )
}

/**
 * Whether pressing Start should also open the floating window: the student asked for it (`popout_on_start`), the window
 * is offered here (`available`: supported, flag on, signed in) and none is open yet.
 */
export const shouldOpenOnStart = (i: { available: boolean; popoutOnStart: boolean; popoutOpen: boolean }): boolean =>
  i.available && i.popoutOnStart && !i.popoutOpen
