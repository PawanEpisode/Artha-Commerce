/**
 * Queue, catch-up, forgotten list, streak and forecast: the twin of `domain/scheduling.py`. Pure functions; the caller
 * supplies `now`, the card views and the student's numbers.
 */

import { retrievability } from './fsrs6'
import {
  CATCHUP_DUE_FACTOR,
  CATCHUP_OVERDUE_DAYS,
  FORGOTTEN_MIN_SCORE,
  IMPORTANCE_WEIGHTS,
  MAX_DAYS_TO_CLEAR,
  NEW_AFTER_REVIEWS,
  OVERDUE_PRIORITY_CAP_DAYS,
  OVERDUE_PRIORITY_PER_DAY,
  PHASE_LEARNING,
  PHASE_NEW,
  PHASE_RELEARNING,
  REVIEW_AHEAD_BATCH,
  SECONDS_PER_DAY,
  STREAK_MIN_REVIEWS,
  SUBJECT_WINDOW,
} from './limits'
import { at } from './util'

export interface CardView {
  id: string
  subject: string
  importance: number // 0 bullet, 1 important, 2 mandatory
  phase: number
  stability: number | null
  lastReviewAt: Date | null
  dueAt: Date | null // effective due; null for a new card
  createdAt?: Date | null
}

export interface Limits {
  newPerDay: number
  reviewsPerDay: number
  newDoneToday?: number
  reviewsDoneToday?: number
}

export interface Catchup {
  active: boolean
  dueCount: number
  oldestOverdueDays: number
  daysToClear: number
}

export interface Queue {
  ids: string[]
  learning: number
  reviews: number
  new: number
  catchup: Catchup
}

const DAY_MS = SECONDS_PER_DAY * 1000

function rNow(card: CardView, now: Date, w20: number): number {
  if (card.stability === null || card.lastReviewAt === null) return 1
  return retrievability(card.stability, Math.max(0, (now.getTime() - card.lastReviewAt.getTime()) / DAY_MS), w20)
}

export function overdueDays(card: CardView, now: Date): number {
  if (card.dueAt === null) return 0
  return Math.max(0, (now.getTime() - card.dueAt.getTime()) / DAY_MS)
}

export function priority(importance: number, r: number, overdue: number): number {
  const weight = at(IMPORTANCE_WEIGHTS, Math.min(Math.max(importance, 0), IMPORTANCE_WEIGHTS.length - 1))
  return weight * (1 - r) + OVERDUE_PRIORITY_PER_DAY * Math.min(overdue, OVERDUE_PRIORITY_CAP_DAYS)
}

export function daysToClear(dueCount: number, reviewsPerDay: number): number {
  if (dueCount <= 0) return 0
  return Math.min(Math.ceil(dueCount / Math.max(reviewsPerDay, 1)), MAX_DAYS_TO_CLEAR)
}

export function catchupState(
  dueCount: number,
  oldestOverdueDays: number,
  reviewsPerDay: number,
  mode: 'auto' | 'on' | 'off' | string = 'auto',
): Catchup {
  const clear = daysToClear(dueCount, reviewsPerDay)
  let active: boolean
  if (mode === 'on') active = dueCount > 0
  else if (mode === 'off') active = false
  else active = dueCount > CATCHUP_DUE_FACTOR * reviewsPerDay || (oldestOverdueDays > CATCHUP_OVERDUE_DAYS && clear > 1)
  return { active, dueCount, oldestOverdueDays, daysToClear: clear }
}

function alternateSubjects(cards: CardView[]): CardView[] {
  const pending = [...cards]
  const out: CardView[] = []
  while (pending.length > 0) {
    let pick = 0
    const last = out[out.length - 1]
    if (last && at(pending, 0).subject === last.subject) {
      for (let i = 1; i < Math.min(pending.length, SUBJECT_WINDOW); i++) {
        if (at(pending, i).subject !== last.subject) {
          pick = i
          break
        }
      }
    }
    const [next] = pending.splice(pick, 1)
    if (next) out.push(next)
  }
  return out
}

const dueMs = (c: CardView): number => c.dueAt?.getTime() ?? 0
const cmpId = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0)

export function planQueue(
  cards: Iterable<CardView>,
  now: Date,
  limits: Limits,
  w20: number,
  options: { mode?: string; dayEnd?: Date | null } = {},
): Queue {
  const learning: CardView[] = []
  const reviews: { p: number; card: CardView }[] = []
  const fresh: CardView[] = []
  const horizon = (options.dayEnd ?? now).getTime()
  for (const card of cards) {
    if (card.phase === PHASE_NEW || card.dueAt === null) fresh.push(card)
    else if (card.phase === PHASE_LEARNING || card.phase === PHASE_RELEARNING) {
      if (card.dueAt.getTime() <= now.getTime()) learning.push(card)
    } else if (card.dueAt.getTime() <= horizon) {
      reviews.push({ p: priority(card.importance, rNow(card, now, w20), overdueDays(card, now)), card })
    }
  }
  let oldest = 0
  for (const { card } of reviews) oldest = Math.max(oldest, overdueDays(card, now))
  const catchup = catchupState(reviews.length, oldest, limits.reviewsPerDay, options.mode ?? 'auto')

  learning.sort((a, b) => dueMs(a) - dueMs(b) || cmpId(a.id, b.id))
  reviews.sort((a, b) => b.p - a.p || dueMs(a.card) - dueMs(b.card) || cmpId(a.card.id, b.card.id))
  const room = Math.max(limits.reviewsPerDay - (limits.reviewsDoneToday ?? 0), 0)
  const orderedReviews = alternateSubjects(reviews.map((r) => r.card).slice(0, room))

  const created = (c: CardView): number => (c.createdAt ?? now).getTime()
  fresh.sort((a, b) => b.importance - a.importance || created(a) - created(b) || cmpId(a.id, b.id))
  const newRoom = catchup.active ? 0 : Math.max(limits.newPerDay - (limits.newDoneToday ?? 0), 0)
  const newCards = fresh.slice(0, newRoom)

  const ids = learning.map((c) => c.id)
  let n = 0
  let sinceNew = 0
  for (const card of orderedReviews) {
    ids.push(card.id)
    sinceNew += 1
    if (sinceNew === NEW_AFTER_REVIEWS) {
      const next = newCards[n]
      if (next) {
        ids.push(next.id)
        n += 1
      }
      sinceNew = 0
    }
  }
  for (; n < newCards.length; n++) ids.push(at(newCards, n).id)
  return { ids, learning: learning.length, reviews: orderedReviews.length, new: newCards.length, catchup }
}

export function reviewAhead(cards: Iterable<CardView>, now: Date, w20: number, size = REVIEW_AHEAD_BATCH): string[] {
  const candidates: [number, string][] = []
  for (const c of cards) {
    if (c.phase === PHASE_NEW || c.phase === PHASE_LEARNING || c.phase === PHASE_RELEARNING) continue
    if (c.dueAt !== null && c.dueAt.getTime() > now.getTime()) candidates.push([rNow(c, now, w20), c.id])
  }
  candidates.sort((a, b) => a[0] - b[0] || cmpId(a[1], b[1]))
  return candidates.slice(0, size).map((c) => c[1])
}

export const forgettingScore = (lapsesInWindow: number, againsInWindow: number): number =>
  2 * lapsesInWindow + againsInWindow

export const isForgotten = (lapsesInWindow: number, againsInWindow: number): boolean =>
  forgettingScore(lapsesInWindow, againsInWindow) >= FORGOTTEN_MIN_SCORE

/** `days` are ISO dates (`YYYY-MM-DD`) of study days; consecutive days with at least `minReviews`, ending today or yesterday. */
export function streak(
  reviewsByDay: Readonly<Record<string, number>>,
  today: string,
  minReviews = STREAK_MIN_REVIEWS,
): number {
  const shift = (iso: string, by: number): string => {
    const d = new Date(`${iso}T00:00:00Z`)
    d.setUTCDate(d.getUTCDate() + by)
    return d.toISOString().slice(0, 10)
  }
  let day = (reviewsByDay[today] ?? 0) >= minReviews ? today : shift(today, -1)
  let count = 0
  while ((reviewsByDay[day] ?? 0) >= minReviews) {
    count += 1
    day = shift(day, -1)
  }
  return count
}

export function forecast(dueDates: Iterable<string | null>, today: string, days = 14): number[] {
  const out = new Array<number>(days).fill(0)
  const base = Date.parse(`${today}T00:00:00Z`)
  for (const due of dueDates) {
    if (due === null) continue
    const offset = Math.max(Math.round((Date.parse(`${due}T00:00:00Z`) - base) / DAY_MS), 0)
    if (offset < days) out[offset] = (out[offset] ?? 0) + 1
  }
  return out
}

/** Study-day helpers (the student's zone and day-start hour). */
function zonedParts(instant: Date, tz: string): { y: number; m: number; d: number; h: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: tz,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant)
  const get = (t: string): number => Number(parts.find((p) => p.type === t)?.value ?? '0')
  return { y: get('year'), m: get('month'), d: get('day'), h: get('hour') }
}

export function localDateOf(instant: Date, tz: string, dayStartHour: number): string {
  const { y, m, d, h } = zonedParts(instant, tz)
  const date = new Date(Date.UTC(y, m - 1, d))
  if (h < dayStartHour) date.setUTCDate(date.getUTCDate() - 1)
  return date.toISOString().slice(0, 10)
}
