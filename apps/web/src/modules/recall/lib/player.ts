/**
 * The local review player: a pure state machine over the cards a session holds. It answers a card with the same scheduler
 * as the server (`fsrs6.ts`, checked against the same golden vectors), so intervals shown offline are the intervals the
 * server's replay will arrive at. It keeps no clock and does no I/O: the caller passes `now` and stores the events.
 *
 * Cards in learning come back in the same session (queued by their due time); a card that leaves the queue counts as done.
 */

import type { ReviewEventBody, ReviewMode } from './api'
import { type Cfg, DEFAULT_CFG, type MemoryState, preview, review } from './fsrs6'
import {
  DURATION_CAP_MS,
  PHASE_LEARNING,
  PHASE_NEW,
  PHASE_RELEARNING,
  UNDO_MAX_EVENTS,
  UNDO_WINDOW_MINUTES,
} from './limits'
import { type CardView, type Catchup, localDateOf, planQueue, reviewAhead } from './queue'
import type { ApiPack, ApiQueueCard, RecallSettings } from './schemas'

export type Rating = 1 | 2 | 3 | 4

/** A learning card due within this many minutes comes back inside the session. */
export const REQUEUE_WITHIN_MINUTES = 20
/** How many cards are assumed to pass per minute when deciding where a card returns (about 30 seconds each). */
const CARDS_PER_MINUTE = 2

export interface Scheduler {
  weights: readonly number[]
  cfg: Cfg
}

export function schedulerOf(settings: RecallSettings, weights: readonly number[]): Scheduler {
  return {
    weights,
    cfg: {
      ...DEFAULT_CFG,
      desiredRetention: settings.desired_retention,
      learningSteps: settings.learning_steps_min,
      relearningSteps: settings.relearning_steps_min,
      maxIntervalDays: settings.max_interval_days,
      fuzz: true,
    },
  }
}

export interface PlayerCard {
  id: string
  itemId: string
  itemVersionId: string
  kind: string
  front: string
  back: string
  importance: number
  badges: string[]
  chapterName: string | null
  subjectKey: string | null
  memory: MemoryState
  dueScheduledAt: Date | null
  postponedUntil: Date | null
  /** The effective due time the server reported; null for a new card. */
  dueAt: Date | null
  rev: number
  wasNew: boolean
  /** How reviews of this card are tagged: `review_ahead` for cards pulled in early, `catchup` in catch-up. */
  mode: ReviewMode
}

const date = (v: string | null): Date | null => (v === null ? null : new Date(v))

export function playerCardOf(c: ApiQueueCard, mode: ReviewMode = 'normal'): PlayerCard {
  return {
    id: c.id,
    itemId: c.item_id,
    itemVersionId: c.item_version_id,
    kind: c.kind,
    front: c.front_md,
    back: c.back_md,
    importance: c.importance,
    badges: c.badges,
    chapterName: c.chapter?.name ?? null,
    subjectKey: c.chapter?.subject_key ?? null,
    memory: {
      phase: c.state,
      step: c.step,
      stability: c.stability,
      difficulty: c.difficulty,
      lastReviewAt: date(c.last_review_at),
      reps: c.reps,
      lapses: c.lapses,
      lastLapseAt: null,
    },
    dueScheduledAt: date(c.due_scheduled_at),
    postponedUntil: date(c.postponed_until),
    dueAt: date(c.due_at),
    rev: c.rev,
    wasNew: c.state === PHASE_NEW,
    mode,
  }
}

interface Answered {
  eventId: string
  cardId: string
  rating: Rating
  at: number
  before: PlayerCard
  queueBefore: string[]
}

export interface PlayerState {
  cards: Readonly<Record<string, PlayerCard>>
  /** Card ids still to show; the first one is the card on screen. */
  queue: readonly string[]
  /** Distinct cards the session set out to show, plus any pulled in later. */
  total: number
  history: readonly Answered[]
  /** Review events given, counting a card every time it was answered. */
  answered: number
  ratings: { again: number; hard: number; good: number; easy: number }
  newSeen: number
}

export function startPlayer(cards: readonly PlayerCard[]): PlayerState {
  const byId: Record<string, PlayerCard> = {}
  const queue: string[] = []
  for (const c of cards) {
    if (byId[c.id]) continue
    byId[c.id] = c
    queue.push(c.id)
  }
  return { cards: byId, queue, total: queue.length, history: [], answered: 0, ratings: zeroRatings(), newSeen: 0 }
}

const zeroRatings = () => ({ again: 0, hard: 0, good: 0, easy: 0 })
const ratingKey = (r: Rating) =>
  (['again', 'hard', 'good', 'easy'] as const)[r - 1] as 'again' | 'hard' | 'good' | 'easy'

export const currentCard = (s: PlayerState): PlayerCard | null => {
  const id = s.queue[0]
  return id === undefined ? null : (s.cards[id] ?? null)
}

/** Cards still to finish, counting each once. */
export const remaining = (s: PlayerState): number => new Set(s.queue).size
export const doneCount = (s: PlayerState): number => Math.max(0, s.total - remaining(s))
export const isFinished = (s: PlayerState): boolean => s.queue.length === 0

/** What each answer would schedule for the card on screen ("10 min", "3 d"), from the local scheduler. */
export function previewLabels(card: PlayerCard, now: Date, sched: Scheduler): Record<Rating, string> {
  const p = preview(card.memory, now, sched.weights, sched.cfg, card.id)
  return { 1: p[1]?.label ?? '', 2: p[2]?.label ?? '', 3: p[3]?.label ?? '', 4: p[4]?.label ?? '' }
}

export interface AnswerContext {
  now: Date
  durationMs: number | null
  sessionId: string | null
  deviceId: string | null
  newId: () => string
  /** Minutes east of UTC at review time. */
  tzOffsetMin: number
  sched: Scheduler
}

export interface AnswerResult {
  state: PlayerState
  event: ReviewEventBody
}

export function answer(s: PlayerState, rating: Rating, ctx: AnswerContext): AnswerResult | null {
  const card = currentCard(s)
  if (!card) return null
  const out = review(card.memory, rating, ctx.now, ctx.sched.weights, ctx.sched.cfg, card.id)
  const next: PlayerCard = {
    ...card,
    memory: out.state,
    dueScheduledAt: out.dueAt,
    postponedUntil: null,
    dueAt: out.dueAt,
    wasNew: false,
  }
  const rest = s.queue.slice(1)
  const minutes = out.scheduledDays * 1440
  let queue = rest
  if (minutes <= REQUEUE_WITHIN_MINUTES) {
    const index = Math.min(rest.length, Math.max(1, Math.round(minutes * CARDS_PER_MINUTE)))
    queue = [...rest.slice(0, index), card.id, ...rest.slice(index)]
  }
  const eventId = ctx.newId()
  const answered: Answered = {
    eventId,
    cardId: card.id,
    rating,
    at: ctx.now.getTime(),
    before: card,
    queueBefore: [...s.queue],
  }
  const ratings = { ...s.ratings }
  ratings[ratingKey(rating)] += 1
  const state: PlayerState = {
    ...s,
    cards: { ...s.cards, [card.id]: next },
    queue,
    history: [...s.history, answered].slice(-UNDO_MAX_EVENTS),
    answered: s.answered + 1,
    ratings,
    newSeen: s.newSeen + (card.wasNew ? 1 : 0),
  }
  return {
    state,
    event: {
      id: eventId,
      card_id: card.id,
      rating,
      reviewed_at: ctx.now.toISOString(),
      duration_ms: ctx.durationMs === null ? null : Math.min(Math.max(Math.round(ctx.durationMs), 0), DURATION_CAP_MS),
      session_id: ctx.sessionId,
      mode: card.mode,
      item_version_id: card.itemVersionId,
      device_id: ctx.deviceId,
      tz_offset_min: ctx.tzOffsetMin,
    },
  }
}

/** The answer that "U" would take back, if the undo window still allows it. */
export function undoable(s: PlayerState, now: Date): Answered | null {
  const last = s.history[s.history.length - 1]
  if (!last) return null
  return now.getTime() - last.at <= UNDO_WINDOW_MINUTES * 60_000 ? last : null
}

export function undo(s: PlayerState, now: Date): { state: PlayerState; undone: Answered } | null {
  const last = undoable(s, now)
  if (!last) return null
  const ratings = { ...s.ratings }
  ratings[ratingKey(last.rating)] = Math.max(0, ratings[ratingKey(last.rating)] - 1)
  return {
    undone: last,
    state: {
      ...s,
      cards: { ...s.cards, [last.cardId]: last.before },
      queue: last.queueBefore,
      history: s.history.slice(0, -1),
      answered: Math.max(0, s.answered - 1),
      ratings,
      newSeen: Math.max(0, s.newSeen - (last.before.wasNew ? 1 : 0)),
    },
  }
}

/** Takes a card out of the session (buried or suspended on the server). */
export function drop(s: PlayerState, cardId: string): PlayerState {
  return { ...s, queue: s.queue.filter((id) => id !== cardId), total: Math.max(0, s.total - 1) }
}

/** Adds cards after the ones already queued ("Review ahead 10 cards"). Cards already in the session are skipped. */
export function extend(s: PlayerState, cards: readonly PlayerCard[]): PlayerState {
  const fresh = cards.filter((c) => !s.cards[c.id])
  if (fresh.length === 0) return s
  const byId = { ...s.cards }
  for (const c of fresh) byId[c.id] = c
  return { ...s, cards: byId, queue: [...s.queue, ...fresh.map((c) => c.id)], total: s.total + fresh.length }
}

// --- planning from a stored pack (offline) -------------------------------------------------------------------------

/** The instant the current study day ends: the next time the local date rolls over, found in 15 minute steps. */
export function dayEndOf(now: Date, tz: string, dayStartHour: number): Date {
  const today = localDateOf(now, tz, dayStartHour)
  for (let m = 15; m <= 26 * 60; m += 15) {
    const t = new Date(now.getTime() + m * 60_000)
    if (localDateOf(t, tz, dayStartHour) !== today) return t
  }
  return new Date(now.getTime() + 24 * 3_600_000)
}

export function cardViewOf(c: ApiQueueCard): CardView {
  return {
    id: c.id,
    subject: c.chapter?.subject_key ?? '',
    importance: c.importance,
    phase: c.state,
    stability: c.stability,
    lastReviewAt: date(c.last_review_at),
    dueAt: date(c.due_at),
  }
}

/** Orders a stored pack into today's session with the same planner the server uses, so a flight-mode session matches. */
export function planFromPack(
  pack: ApiPack,
  now: Date,
  cap = 50,
): { cards: PlayerCard[]; mode: ReviewMode; catchup: Catchup } {
  const s = pack.settings
  const queue = planQueue(
    pack.cards.map(cardViewOf),
    now,
    {
      newPerDay: s.new_per_day,
      reviewsPerDay: s.reviews_per_day,
      newDoneToday: pack.counters.new_done_today,
      reviewsDoneToday: pack.counters.reviews_done_today,
    },
    pack.weights[20] ?? 0.1542,
    { mode: s.catchup_mode, dayEnd: dayEndOf(now, s.tz, s.day_start_hour) },
  )
  const byId = new Map(pack.cards.map((c) => [c.id, c]))
  const mode: ReviewMode = queue.catchup.active ? 'catchup' : 'normal'
  const cards = queue.ids
    .slice(0, cap)
    .map((id) => byId.get(id))
    .filter((c): c is ApiQueueCard => c !== undefined)
    .map((c) => playerCardOf(c, mode))
  return { cards, mode, catchup: queue.catchup }
}

/** Ten cards due soon, weakest memory first, from the stored pack. */
export function aheadFromPack(pack: ApiPack, now: Date, exclude: ReadonlySet<string>, size = 10): PlayerCard[] {
  const views = pack.cards.filter((c) => !exclude.has(c.id)).map(cardViewOf)
  const ids = reviewAhead(views, now, pack.weights[20] ?? 0.1542, size)
  const byId = new Map(pack.cards.map((c) => [c.id, c]))
  return ids
    .map((id) => byId.get(id))
    .filter((c): c is ApiQueueCard => c !== undefined)
    .map((c) => playerCardOf(c, 'review_ahead'))
}

export const isLearning = (c: PlayerCard) => c.memory.phase === PHASE_LEARNING || c.memory.phase === PHASE_RELEARNING
