/**
 * Exam awareness: the twin of `apps/api/modules/recall/domain/exam.py`. The horizon, the retention boost, `R_exam`, the quick
 * revision set, the cram window and pacing, as pure functions of the numbers passed in. `vectors/exam_cases.json` is shared with
 * the Python side and `exam.test.ts` holds this file to it.
 */

import type { Cfg } from './fsrs6'
import { retrievability } from './fsrs6'
import {
  CRAM_HOURS,
  EXAM_BOOST_DAYS,
  EXAM_BOOST_RETENTION,
  EXAM_HORIZON_DAYS,
  EXAM_LAST_REVIEW_DAYS,
  EXAM_WINDOW_END_DAYS,
  EXAM_WINDOW_SLOTS,
  EXAM_WINDOW_START_DAYS,
  IMPORTANCE_WEIGHTS,
  PACING_LEAD_DAYS,
  PHASE_NEW,
  QUICK_MIN_CARDS,
  QUICK_MIN_IMPORTANCE,
  QUICK_R_TARGET,
  SECONDS_PER_DAY,
} from './limits'

const MANDATORY = 2
const DAY_MS = SECONDS_PER_DAY * 1000

export function daysBetween(later: Date, earlier: Date): number {
  return (later.getTime() - earlier.getTime()) / DAY_MS
}

export function daysToExam(now: Date, examAt: Date | null): number | null {
  return examAt === null ? null : daysBetween(examAt, now)
}

const addDays = (t: Date, days: number): Date => new Date(t.getTime() + days * DAY_MS)

/** 0 to 4: the day of the final window a card is spread to (first 8 hex digits of its id, the same as Python). */
export function slotOf(cardId: string): number {
  return parseInt(cardId.replace(/-/g, '').slice(0, 8), 16) % EXAM_WINDOW_SLOTS
}

export function horizon(
  dueAt: Date | null,
  lastReviewAt: Date | null,
  examAt: Date | null,
  cardId: string,
  now: Date,
  enabled = true,
): Date | null {
  if (!enabled || dueAt === null || examAt === null) return dueAt
  const left = daysBetween(examAt, now)
  if (!(left > CRAM_HOURS / 24 && left <= EXAM_HORIZON_DAYS)) return dueAt
  if (dueAt.getTime() <= addDays(examAt, -EXAM_WINDOW_END_DAYS).getTime()) return dueAt
  if (lastReviewAt !== null && lastReviewAt.getTime() > addDays(examAt, -EXAM_LAST_REVIEW_DAYS).getTime()) return dueAt
  const window = addDays(examAt, -EXAM_WINDOW_START_DAYS + slotOf(cardId))
  const earliest = addDays(now, 1)
  const target = window.getTime() > earliest.getTime() ? window : earliest
  return target.getTime() < dueAt.getTime() ? target : dueAt
}

export function retentionFor(importance: number, desired: number, leftDays: number | null, enabled = true): number {
  if (enabled && importance === MANDATORY && leftDays !== null && leftDays > 0 && leftDays <= EXAM_BOOST_DAYS) {
    return Math.max(desired, EXAM_BOOST_RETENTION)
  }
  return desired
}

export function cfgAt(cfg: Cfg, importance: number, at: Date, examAt: Date | null, enabled = true): Cfg {
  const wanted = retentionFor(importance, cfg.desiredRetention, daysToExam(at, examAt), enabled)
  return wanted === cfg.desiredRetention ? cfg : { ...cfg, desiredRetention: wanted }
}

export function rExam(stability: number | null, lastReviewAt: Date | null, examAt: Date, w20: number): number | null {
  if (stability === null || lastReviewAt === null) return null
  return retrievability(stability, daysBetween(examAt, lastReviewAt), w20)
}

export interface QuickCard {
  id: string
  importance: number
  phase: number
  stability: number | null
  lastReviewAt: Date | null
}

export interface QuickPlan {
  ids: string[]
  candidates: number
  selected: number
  cutOff: number
  daysToExam: number
  windowDays: number
  perDay: number
  minutesPerDay: number
  tooFew: boolean
}

export function quickSet(
  cards: Iterable<QuickCard>,
  examAt: Date,
  minutesPerDay: number,
  medianSeconds: number,
  now: Date,
  w20: number,
): QuickPlan {
  const left = daysBetween(examAt, now)
  const windowDays = Math.max(Math.floor(left) - EXAM_WINDOW_END_DAYS, 0)
  const scored: [number, string][] = []
  for (const c of cards) {
    if (c.importance < QUICK_MIN_IMPORTANCE) continue
    const weight = IMPORTANCE_WEIGHTS[Math.min(Math.max(c.importance, 0), IMPORTANCE_WEIGHTS.length - 1)] ?? 0
    if (c.phase === PHASE_NEW) {
      if (c.importance === MANDATORY) scored.push([weight, c.id])
      continue
    }
    const r = rExam(c.stability, c.lastReviewAt, examAt, w20)
    if (r !== null && r < QUICK_R_TARGET) scored.push([weight * (1 - r), c.id])
  }
  // Python sorts by (-risk, id); ids compare as strings in both languages
  scored.sort((a, b) => (b[0] !== a[0] ? b[0] - a[0] : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0))
  const seconds = Math.max(medianSeconds, 1)
  const size = windowDays ? Math.floor((minutesPerDay * windowDays * 60) / seconds) : 0
  const ids = scored.slice(0, size).map((t) => t[1])
  return {
    ids,
    candidates: scored.length,
    selected: ids.length,
    cutOff: scored.length - ids.length,
    daysToExam: Math.max(Math.floor(left), 0),
    windowDays,
    perDay: windowDays ? Math.ceil(ids.length / windowDays) : 0,
    minutesPerDay: windowDays ? Math.ceil((ids.length * seconds) / 60 / windowDays) : 0,
    tooFew: scored.length < QUICK_MIN_CARDS,
  }
}

export function cramOpen(now: Date, examAt: Date | null): boolean {
  const left = daysToExam(now, examAt)
  return left !== null && left > 0 && left <= CRAM_HOURS / 24
}

export interface Pacing {
  unseen: number
  windowDays: number
  newPerDay: number
  introducedAtLimit: number
  neededPerDay: number
  feasible: boolean
}

export function pacing(unseenInScope: number, daysLeft: number, newPerDay: number): Pacing {
  const windowDays = Math.max(Math.floor(daysLeft) - PACING_LEAD_DAYS, 0)
  const unseen = Math.max(unseenInScope, 0)
  const atLimit = Math.min(unseen, newPerDay * windowDays)
  const needed = unseen === 0 ? 0 : windowDays ? Math.ceil(unseen / windowDays) : unseen
  return {
    unseen,
    windowDays,
    newPerDay,
    introducedAtLimit: atLimit,
    neededPerDay: needed,
    feasible: atLimit >= unseen,
  }
}
