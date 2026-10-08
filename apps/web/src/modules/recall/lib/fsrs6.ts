/**
 * FSRS-6 as a pure, versioned function: the twin of `apps/api/modules/recall/domain/fsrs6.py`. Both are our own code, pinned by
 * the same golden vectors (`vectors/fsrs6_cases.json`); `ts-fsrs` is only an oracle in the tests. Instants are `Date`s (UTC
 * milliseconds); intervals are whole days rounded half up; fuzz is a deterministic hash of the card id and the review count.
 */

import {
  AGAIN,
  EASY,
  GOOD,
  HARD,
  MINUTES_PER_DAY,
  PHASE_LEARNING,
  PHASE_NEW,
  PHASE_RELEARNING,
  PHASE_REVIEW,
  SCHEDULER_VERSION,
  SECONDS_PER_DAY,
} from './limits'
import { at } from './util'

export { SCHEDULER_VERSION }

export const DEFAULT_WEIGHTS: readonly number[] = [
  0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483,
  0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542,
]

const STABILITY_MIN = 0.001
const LOWER = [
  STABILITY_MIN,
  STABILITY_MIN,
  STABILITY_MIN,
  STABILITY_MIN,
  1.0,
  0.001,
  0.001,
  0.001,
  0.0,
  0.0,
  0.001,
  0.001,
  0.001,
  0.001,
  0.0,
  0.0,
  1.0,
  0.0,
  0.0,
  0.0,
  0.1,
]
const UPPER = [100, 100, 100, 100, 10, 4, 4, 0.75, 4.5, 0.8, 3.5, 5, 0.25, 0.9, 4, 1, 6, 2, 2, 0.8, 0.8]
const MIN_DIFFICULTY = 1.0
const MAX_DIFFICULTY = 10.0
const FUZZ_RANGES: readonly (readonly [number, number, number])[] = [
  [2.5, 7.0, 0.15],
  [7.0, 20.0, 0.1],
  [20.0, Infinity, 0.05],
]

export interface MemoryState {
  phase: number
  step: number | null
  stability: number | null
  difficulty: number | null
  lastReviewAt: Date | null
  reps: number
  lapses: number
  lastLapseAt: Date | null
}

export interface Cfg {
  desiredRetention: number
  learningSteps: readonly number[] // minutes
  relearningSteps: readonly number[] // minutes
  maxIntervalDays: number
  fuzz: boolean
}

export interface ReviewOutcome {
  state: MemoryState
  scheduledDays: number
  dueAt: Date
  phaseBefore: number
  elapsedDays: number | null
  retrievabilityBefore: number | null
  lapsed: boolean
}

export interface Preview {
  rating: number
  scheduledDays: number
  dueAt: Date
  label: string
}

export const DEFAULT_CFG: Cfg = {
  desiredRetention: 0.9,
  learningSteps: [1, 10],
  relearningSteps: [10],
  maxIntervalDays: 365,
  fuzz: true,
}

export function newMemoryState(): MemoryState {
  return {
    phase: PHASE_NEW,
    step: null,
    stability: null,
    difficulty: null,
    lastReviewAt: null,
    reps: 0,
    lapses: 0,
    lastLapseAt: null,
  }
}

export function validateWeights(w: readonly number[]): number[] {
  if (w.length !== LOWER.length) throw new Error(`Expected ${LOWER.length} weights, got ${w.length}.`)
  const bad = w
    .map((x, i) =>
      x >= at(LOWER, i) && x <= at(UPPER, i) ? null : `w[${i}]=${x} is outside [${LOWER[i]}, ${UPPER[i]}]`,
    )
    .filter((x): x is string => x !== null)
  if (bad.length > 0) throw new Error(`Weights out of bounds: ${bad.join('; ')}`)
  return [...w]
}

const roundHalfUp = (x: number): number => Math.floor(x + 0.5)
const factor = (w20: number): number => 0.9 ** (-1 / w20) - 1

export function elapsedWholeDays(last: Date | null, now: Date): number | null {
  if (last === null) return null
  return Math.max(0, Math.floor((now.getTime() - last.getTime()) / 1000 / SECONDS_PER_DAY))
}

export function retrievability(stability: number, elapsedDays: number, w20: number): number {
  return (1 + (factor(w20) * Math.max(0, elapsedDays)) / stability) ** -w20
}

export function intervalDays(stability: number, retention: number, w20: number, maxInterval: number): number {
  const raw = (stability / factor(w20)) * (retention ** (-1 / w20) - 1)
  return Math.min(Math.max(roundHalfUp(raw), 1), maxInterval)
}

/** FNV-1a (32 bit) over the UTF-8 bytes of `"{cardId}:{reps}"`, divided by 2^32. */
export function fuzzUnit(cardId: string, reps: number): number {
  let h = 0x811c9dc5
  for (const byte of new TextEncoder().encode(`${cardId}:${reps}`)) {
    h = Math.imul(h ^ byte, 0x01000193) >>> 0
  }
  return h / 4294967296
}

function fuzzed(days: number, maxInterval: number, cardId: string, reps: number): number {
  if (days < 2.5) return days
  let delta = 1.0
  for (const [start, end, f] of FUZZ_RANGES) delta += f * Math.max(Math.min(days, end) - start, 0)
  const hi = Math.min(roundHalfUp(days + delta), maxInterval)
  const lo = Math.min(Math.max(2, roundHalfUp(days - delta)), hi)
  return Math.min(roundHalfUp(fuzzUnit(cardId, reps) * (hi - lo + 1) + lo), maxInterval)
}

const clampD = (d: number): number => Math.min(Math.max(d, MIN_DIFFICULTY), MAX_DIFFICULTY)
const clampS = (s: number): number => Math.max(s, STABILITY_MIN)

const initStability = (w: readonly number[], rating: number): number => clampS(at(w, rating - 1))

function initDifficulty(w: readonly number[], rating: number, clamp: boolean): number {
  const d = at(w, 4) - Math.exp(at(w, 5) * (rating - 1)) + 1
  return clamp ? clampD(d) : d
}

function nextDifficulty(w: readonly number[], d: number, rating: number): number {
  const delta = -(at(w, 6) * (rating - 3))
  const target = d + ((10 - d) * delta) / 9
  return clampD(at(w, 7) * initDifficulty(w, EASY, false) + (1 - at(w, 7)) * target)
}

function shortTermStability(w: readonly number[], s: number, rating: number): number {
  let inc = Math.exp(at(w, 17) * (rating - 3 + at(w, 18))) * s ** -at(w, 19)
  if (rating >= HARD) inc = Math.max(inc, 1)
  return clampS(s * inc)
}

function recallStability(w: readonly number[], d: number, s: number, r: number, rating: number): number {
  const hard = rating === HARD ? at(w, 15) : 1
  const easy = rating === EASY ? at(w, 16) : 1
  return s * (1 + Math.exp(at(w, 8)) * (11 - d) * s ** -at(w, 9) * (Math.exp((1 - r) * at(w, 10)) - 1) * hard * easy)
}

function forgetStability(w: readonly number[], d: number, s: number, r: number): number {
  const longTerm = at(w, 11) * d ** -at(w, 12) * ((s + 1) ** at(w, 13) - 1) * Math.exp((1 - r) * at(w, 14))
  const shortTerm = s / Math.exp(at(w, 17) * at(w, 18))
  return Math.min(longTerm, shortTerm)
}

function nextStability(w: readonly number[], d: number, s: number, r: number, rating: number): number {
  return clampS(rating === AGAIN ? forgetStability(w, d, s, r) : recallStability(w, d, s, r, rating))
}

function hardMinutes(steps: readonly number[], step: number): number {
  if (step === 0 && steps.length === 1) return at(steps, 0) * 1.5
  if (step === 0 && steps.length >= 2) return (at(steps, 0) + at(steps, 1)) / 2
  return at(steps, step)
}

export function review(
  state: MemoryState,
  rating: number,
  now: Date,
  w: readonly number[],
  cfg: Cfg,
  cardId: string,
): ReviewOutcome {
  if (![1, 2, 3, 4].includes(rating)) throw new Error(`Unknown rating: ${rating}`)
  const w20 = at(w, 20)
  const phaseBefore = state.phase
  const phase = state.phase === PHASE_NEW ? PHASE_LEARNING : state.phase
  const step = state.step ?? 0
  const elapsed = elapsedWholeDays(state.lastReviewAt, now)
  let s = state.stability
  let d = state.difficulty
  const rBefore = s !== null && elapsed !== null ? retrievability(s, elapsed, w20) : null

  if (s === null || d === null) {
    s = initStability(w, rating)
    d = initDifficulty(w, rating, true)
  } else {
    const s2 =
      elapsed !== null && elapsed < 1 ? shortTermStability(w, s, rating) : nextStability(w, d, s, rBefore ?? 1, rating)
    d = nextDifficulty(w, d, rating)
    s = s2
  }

  const lapsed = phase === PHASE_REVIEW && rating === AGAIN
  let newPhase = phase
  let newStep: number | null = phase !== PHASE_REVIEW ? step : null
  let minutes: number | null = null

  if (phase === PHASE_REVIEW) {
    if (lapsed && cfg.relearningSteps.length > 0) {
      newPhase = PHASE_RELEARNING
      newStep = 0
      minutes = at(cfg.relearningSteps, 0)
    }
  } else {
    const steps = phase === PHASE_LEARNING ? cfg.learningSteps : cfg.relearningSteps
    if (steps.length === 0 || (step >= steps.length && rating >= HARD)) {
      // graduates
    } else if (rating === AGAIN) {
      newStep = 0
      minutes = at(steps, 0)
    } else if (rating === HARD) {
      minutes = hardMinutes(steps, step)
    } else if (rating === GOOD && step + 1 < steps.length) {
      newStep = step + 1
      minutes = at(steps, step + 1)
    }
  }

  let scheduled: number
  if (minutes === null) {
    newPhase = PHASE_REVIEW
    newStep = null
    let days = intervalDays(s, cfg.desiredRetention, w20, cfg.maxIntervalDays)
    if (cfg.fuzz) days = fuzzed(days, cfg.maxIntervalDays, cardId, state.reps)
    scheduled = days
  } else {
    scheduled = minutes / MINUTES_PER_DAY
  }

  return {
    state: {
      phase: newPhase,
      step: newStep,
      stability: s,
      difficulty: d,
      lastReviewAt: now,
      reps: state.reps + 1,
      lapses: state.lapses + (lapsed ? 1 : 0),
      lastLapseAt: lapsed ? now : state.lastLapseAt,
    },
    scheduledDays: scheduled,
    dueAt: new Date(now.getTime() + scheduled * SECONDS_PER_DAY * 1000),
    phaseBefore,
    elapsedDays: elapsed,
    retrievabilityBefore: rBefore,
    lapsed,
  }
}

export function formatInterval(days: number): string {
  const minutes = roundHalfUp(days * MINUTES_PER_DAY)
  if (minutes < 60) return `${Math.max(minutes, 1)} min`
  if (minutes < MINUTES_PER_DAY) return `${roundHalfUp(minutes / 60)} h`
  const whole = roundHalfUp(days)
  if (whole < 31) return `${whole} d`
  if (whole < 365) return `${roundHalfUp(whole / 30.4375)} mo`
  return `${roundHalfUp((whole / 365) * 10) / 10} y`
}

export function preview(
  state: MemoryState,
  now: Date,
  w: readonly number[],
  cfg: Cfg,
  cardId: string,
): Record<number, Preview> {
  const out: Record<number, Preview> = {}
  for (const rating of [1, 2, 3, 4]) {
    const o = review(state, rating, now, w, cfg, cardId)
    out[rating] = { rating, scheduledDays: o.scheduledDays, dueAt: o.dueAt, label: formatInterval(o.scheduledDays) }
  }
  return out
}

export function capStability(state: MemoryState, capDays: number): MemoryState {
  if (state.stability === null || state.stability <= capDays) return state
  return { ...state, stability: capDays }
}
