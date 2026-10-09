/**
 * Sends what happened offline: opens sessions the server has not seen, then the waiting review events in order, 100 to a
 * request, then closes finished sessions. Every event id is an idempotency key, so a response that never arrived is simply
 * sent again and counted once. Every status the server can give an event is final, so a handled event leaves the store.
 */

import { ApiError } from '~/lib/api'

import { recallApi, type ReviewEventBody } from './api'
import { eventStore, type StoredEvent } from './eventStore'
import { BATCH_MAX_EVENTS } from './limits'
import type { ReviewCardPatch, ReviewResult } from './schemas'

export type SyncFailure = 'network' | 'throttled' | 'server' | 'refused'

export interface FlushResult {
  /** Events the server answered for in this run. */
  sent: number
  applied: number
  duplicate: number
  /** The card's text changed after the review, so it counted for nothing. */
  stale: number
  /** The review was older than the server accepts. */
  late: number
  /** The card was deleted; the review is kept in the log only. */
  deleted: number
  invalid: number
  /** Events still waiting on this device. */
  remaining: number
  failure: SyncFailure | null
  /** Seconds the server asked us to wait (429). */
  retryAfter?: number
  cards: ReviewCardPatch[]
}

const empty = (): FlushResult => ({
  sent: 0,
  applied: 0,
  duplicate: 0,
  stale: 0,
  late: 0,
  deleted: 0,
  invalid: 0,
  remaining: 0,
  failure: null,
  cards: [],
})

export function failureOf(error: unknown): { failure: SyncFailure; retryAfter?: number } {
  if (!(error instanceof ApiError)) return { failure: 'network' }
  if (error.status === 429) return { failure: 'throttled', retryAfter: error.retryAfter }
  if (error.status === 0 || error.status === 408) return { failure: 'network' }
  if (error.status >= 500) return { failure: 'server' }
  return { failure: 'refused' }
}

function tally(out: FlushResult, r: ReviewResult) {
  out.sent += 1
  if (r.status === 'applied') out.applied += 1
  else if (r.status === 'duplicate') out.duplicate += 1
  else if (r.status === 'stale_content') out.stale += 1
  else if (r.status === 'late_unapplied') out.late += 1
  else if (r.status === 'applied_to_deleted') out.deleted += 1
  else out.invalid += 1
}

let running: Promise<FlushResult> | null = null

/** One flush at a time: a second call while one runs waits for it and shares its result. */
export function flush(userId: string): Promise<FlushResult> {
  running ??= run(userId).finally(() => {
    running = null
  })
  return running
}

async function run(userId: string): Promise<FlushResult> {
  const out = empty()
  try {
    await openSessions(userId)
    for (;;) {
      const batch = (await eventStore.pendingEvents(userId)).slice(0, BATCH_MAX_EVENTS)
      if (batch.length === 0) break
      const response = await recallApi.submitBatch(batch.map((e) => e.body))
      const answered = new Set(response.results.map((r) => r.event_id))
      for (const r of response.results) tally(out, r)
      out.cards.push(...response.cards)
      const handled = batch.filter((e: StoredEvent) => answered.has(e.id)).map((e) => e.id)
      await eventStore.removeEvents(handled)
      await eventStore.patchPack(userId, response.cards)
      // A response that answers none of the batch would loop forever; leave the rest for the next run
      if (handled.length === 0) break
    }
    await closeSessions(userId)
  } catch (error) {
    const f = failureOf(error)
    out.failure = f.failure
    out.retryAfter = f.retryAfter
  }
  out.remaining = await eventStore.pendingCount(userId)
  return out
}

async function openSessions(userId: string) {
  for (const s of await eventStore.sessionsFor(userId)) {
    if (s.opened) continue
    await recallApi.openSession({ client_id: s.id, source: s.source, planned_count: s.plannedCount })
    await eventStore.saveSession({ ...s, opened: true })
  }
}

async function closeSessions(userId: string) {
  const waiting = new Set((await eventStore.pendingEvents(userId)).map((e) => e.body.session_id))
  for (const s of await eventStore.sessionsFor(userId)) {
    if (!s.closed || s.closeSent || !s.opened || waiting.has(s.id)) continue
    await recallApi.closeSession(s.id)
    await eventStore.saveSession({ ...s, closeSent: true })
  }
}

/** Test and screen helper: the bodies still waiting, oldest first. */
export async function waiting(userId: string): Promise<ReviewEventBody[]> {
  return (await eventStore.pendingEvents(userId)).map((e) => e.body)
}
