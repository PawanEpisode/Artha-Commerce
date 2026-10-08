/**
 * Replay: the twin of `domain/folding.py`. A card's memory is a pure function of its facts, so the offline player and the
 * server rebuild the same state from the same events, in any input order and with duplicates.
 */

import { capStability, type Cfg, type MemoryState, newMemoryState, review } from './fsrs6'
import { CONTENT_RESET_STABILITY_CAP_DAYS, PHASE_NEW } from './limits'

export interface ReviewEvent {
  type: 'review'
  id: string
  at: Date
  rating: number
  countsForScheduling?: boolean
  voided?: boolean
}

/** Only `forget`, `content_reset`, `postpone` and `unpostpone` change state; every other kind is audit only. */
export interface ScheduleEvent {
  type: 'schedule'
  id: string
  at: Date
  kind: string
  toDue?: Date | null
  capDays?: number | null
}

export type CardEvent = ReviewEvent | ScheduleEvent

export interface CardState {
  memory: MemoryState
  dueScheduledAt: Date | null
  postponedUntil: Date | null
}

export function newCardState(): CardState {
  return { memory: newMemoryState(), dueScheduledAt: null, postponedUntil: null }
}

export function effectiveDue(state: CardState): Date | null {
  if (state.dueScheduledAt === null) return null
  if (state.postponedUntil === null) return state.dueScheduledAt
  return state.postponedUntil.getTime() > state.dueScheduledAt.getTime() ? state.postponedUntil : state.dueScheduledAt
}

function compare(a: CardEvent, b: CardEvent): number {
  const t = a.at.getTime() - b.at.getTime()
  if (t !== 0) return t
  const ka = a.type === 'schedule' ? 0 : 1
  const kb = b.type === 'schedule' ? 0 : 1
  if (ka !== kb) return ka - kb
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

export function applyEvent(
  state: CardState,
  event: CardEvent,
  w: readonly number[],
  cfg: Cfg,
  cardId: string,
): CardState {
  if (event.type === 'review') {
    if (event.countsForScheduling === false || event.voided === true) return state
    const out = review(state.memory, event.rating, event.at, w, cfg, cardId)
    return { memory: out.state, dueScheduledAt: out.dueAt, postponedUntil: null }
  }
  if (event.kind === 'forget') return newCardState()
  if (event.kind === 'content_reset') {
    const memory = capStability(state.memory, event.capDays || CONTENT_RESET_STABILITY_CAP_DAYS)
    if (memory.phase === PHASE_NEW) return { ...state, memory }
    return { memory, dueScheduledAt: event.at, postponedUntil: null }
  }
  if (event.kind === 'postpone') return { ...state, postponedUntil: event.toDue ?? null }
  if (event.kind === 'unpostpone') return { ...state, postponedUntil: null }
  return state
}

export function fold(events: Iterable<CardEvent>, w: readonly number[], cfg: Cfg, cardId: string): CardState {
  const seen = new Set<string>()
  let state = newCardState()
  for (const event of [...events].sort(compare)) {
    const key = `${event.type === 'schedule' ? 's' : 'r'}:${event.id}`
    if (seen.has(key)) continue
    seen.add(key)
    state = applyEvent(state, event, w, cfg, cardId)
  }
  return state
}
