import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { ReviewEventBody } from './api'
import { eventStore, resetEventStore } from './eventStore'
import { flush } from './sync'

const submitBatch = vi.hoisted(() => vi.fn())
const openSession = vi.hoisted(() => vi.fn())
const closeSession = vi.hoisted(() => vi.fn())

vi.mock('./api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  recallApi: { submitBatch, openSession, closeSession },
}))

const body = (n: number, session: string | null = 's1'): ReviewEventBody => ({
  id: `e-${String(n).padStart(4, '0')}`,
  card_id: `c-${n}`,
  rating: 3,
  reviewed_at: new Date(1_790_000_000_000 + n * 1000).toISOString(),
  duration_ms: 1000,
  session_id: session,
  mode: 'normal',
  item_version_id: null,
  device_id: null,
  tz_offset_min: 330,
})

const card = (id: string) => ({
  id,
  rev: 2,
  state: 2,
  state_name: 'review',
  status: 'active',
  due_at: null,
  buried_until: null,
  reps: 1,
  lapses: 0,
  leech: false,
  needs_recheck: false,
})

/** An honest server: answers every event, once, as `applied` or `duplicate` if it saw the id before. */
function honestServer() {
  const seen = new Set<string>()
  const stored: string[] = []
  submitBatch.mockImplementation(async (events: ReviewEventBody[]) => ({
    results: events.map((e) => {
      const dup = seen.has(e.id)
      seen.add(e.id)
      if (!dup) stored.push(e.id)
      return { event_id: e.id, status: dup ? 'duplicate' : 'applied', reason: '', merged: false, card: null }
    }),
    cards: events.map((e) => card(e.card_id)),
    server_time: '2026-10-09T08:00:00Z',
  }))
  return stored
}

beforeEach(async () => {
  resetEventStore()
  await eventStore.clear()
  submitBatch.mockReset()
  openSession.mockReset().mockResolvedValue({})
  closeSession.mockReset().mockResolvedValue({})
})

describe('flush', () => {
  it('sends 250 queued events in three batches of at most 100, in order', async () => {
    const stored = honestServer()
    for (let n = 1; n <= 250; n++) await eventStore.addEvent('u1', body(n))
    const result = await flush('u1')
    expect(submitBatch.mock.calls.map((c) => c[0].length)).toEqual([100, 100, 50])
    expect(stored).toEqual(Array.from({ length: 250 }, (_, i) => `e-${String(i + 1).padStart(4, '0')}`))
    expect(result).toMatchObject({ sent: 250, applied: 250, remaining: 0, failure: null })
    expect(await eventStore.pendingCount('u1')).toBe(0)
  })

  it('creates no duplicates when a response is dropped and the batch is sent again', async () => {
    const stored = honestServer()
    for (let n = 1; n <= 5; n++) await eventStore.addEvent('u1', body(n))
    const honest = submitBatch.getMockImplementation()!
    submitBatch.mockImplementationOnce(async (events: ReviewEventBody[]) => {
      await honest(events) // the server stored them ...
      throw new TypeError('Failed to fetch') // ... but the answer never arrived
    })
    const first = await flush('u1')
    expect(first.failure).toBe('network')
    expect(first.remaining).toBe(5)
    const second = await flush('u1')
    expect(second).toMatchObject({ duplicate: 5, applied: 0, remaining: 0, failure: null })
    expect(stored).toHaveLength(5)
  })

  it('counts every kind of answer and merges the card rows it was given', async () => {
    await eventStore.savePack('u1', {
      pack_id: 'p',
      generated_at: 'x',
      server_time: 'x',
      expires_at: 'x',
      settings: {} as never,
      weights: [],
      scheduler_version: 'v',
      cards: [],
      counters: { new_done_today: 0, reviews_done_today: 0, local_date: 'x' },
    })
    for (let n = 1; n <= 5; n++) await eventStore.addEvent('u1', body(n))
    submitBatch.mockResolvedValueOnce({
      results: ['applied', 'stale_content', 'late_unapplied', 'applied_to_deleted', 'invalid'].map((status, i) => ({
        event_id: `e-000${i + 1}`,
        status,
        reason: '',
        merged: false,
        card: null,
      })),
      cards: [card('c-1')],
      server_time: '2026-10-09T08:00:00Z',
    })
    const r = await flush('u1')
    expect(r).toMatchObject({ applied: 1, stale: 1, late: 1, deleted: 1, invalid: 1, remaining: 0 })
    expect(r.cards.map((c) => c.id)).toEqual(['c-1'])
  })

  it('keeps events when the server is down or throttles, and says why', async () => {
    await eventStore.addEvent('u1', body(1))
    submitBatch.mockRejectedValueOnce(new ApiError(503, 'down'))
    expect(await flush('u1')).toMatchObject({ failure: 'server', remaining: 1 })
    const throttled = new ApiError(429, 'slow')
    throttled.retryAfter = 12
    submitBatch.mockRejectedValueOnce(throttled)
    expect(await flush('u1')).toMatchObject({ failure: 'throttled', retryAfter: 12, remaining: 1 })
    submitBatch.mockRejectedValueOnce(new ApiError(404, 'flag off'))
    expect(await flush('u1')).toMatchObject({ failure: 'refused', remaining: 1 })
  })

  it('opens a session before its reviews and closes it after the last one is sent', async () => {
    const order: string[] = []
    openSession.mockImplementation(async () => void order.push('open'))
    closeSession.mockImplementation(async () => void order.push('close'))
    submitBatch.mockImplementation(async (events: ReviewEventBody[]) => {
      order.push('batch')
      return {
        results: events.map((e) => ({ event_id: e.id, status: 'applied', reason: '', merged: false, card: null })),
        cards: [],
        server_time: '2026-10-09T08:00:00Z',
      }
    })
    await eventStore.saveSession({
      id: 's1',
      userId: 'u1',
      source: 'today',
      startedAt: 1,
      plannedCount: 3,
      opened: false,
      closed: true,
      closeSent: false,
      summary: null,
    })
    await eventStore.addEvent('u1', body(1))
    await flush('u1')
    expect(order).toEqual(['open', 'batch', 'close'])
    expect(await eventStore.getSession('s1')).toMatchObject({ opened: true, closeSent: true })
  })

  it('shares one run between two callers', async () => {
    honestServer()
    await eventStore.addEvent('u1', body(1))
    const [a, b] = await Promise.all([flush('u1'), flush('u1')])
    expect(a).toBe(b)
    expect(submitBatch).toHaveBeenCalledTimes(1)
  })
})
