import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'

import type { ReviewEventBody } from './api'
import { eventStore, isStale, QuotaError, resetEventStore, STALE_PACK_MS } from './eventStore'
import { OFFLINE_EVENT_CAP } from './limits'
import { apiCard, apiPack } from './testing'

const body = (n: number, over: Partial<ReviewEventBody> = {}): ReviewEventBody => ({
  id: `e-${String(n).padStart(5, '0')}`,
  card_id: `c-${n % 50}`,
  rating: 3,
  reviewed_at: new Date(1_790_000_000_000 + n * 1000).toISOString(),
  duration_ms: 3000,
  session_id: 's1',
  mode: 'normal',
  item_version_id: null,
  device_id: 'd',
  tz_offset_min: 330,
  ...over,
})

beforeEach(async () => {
  resetEventStore()
  await eventStore.clear()
})

describe('pending events', () => {
  it('come back in the order they were added, for their own user only', async () => {
    await eventStore.addEvent('u1', body(2))
    await eventStore.addEvent('u2', body(9))
    await eventStore.addEvent('u1', body(1))
    expect((await eventStore.pendingEvents('u1')).map((e) => e.id)).toEqual(['e-00002', 'e-00001'])
    expect(await eventStore.pendingCount('u2')).toBe(1)
  })

  it('keep one row when the same review is stored twice', async () => {
    await eventStore.addEvent('u1', body(1))
    await eventStore.addEvent('u1', body(1))
    expect(await eventStore.pendingCount('u1')).toBe(1)
  })

  it('keep their order after a reload of the module state', async () => {
    await eventStore.addEvent('u1', body(1))
    resetEventStore()
    await eventStore.addEvent('u1', body(2))
    expect((await eventStore.pendingEvents('u1')).map((e) => e.id)).toEqual(['e-00001', 'e-00002'])
  })

  it('refuse a new review once 5,000 wait, with a message, and accept it again after some are sent', async () => {
    for (let n = 1; n <= OFFLINE_EVENT_CAP; n++) await eventStore.addEvent('u1', body(n))
    await expect(eventStore.addEvent('u1', body(OFFLINE_EVENT_CAP + 1))).rejects.toBeInstanceOf(QuotaError)
    await expect(eventStore.addEvent('u1', body(OFFLINE_EVENT_CAP + 1))).rejects.toThrow(
      /5000 reviews that have not synced/,
    )
    await eventStore.removeEvents(['e-00001'])
    await expect(eventStore.addEvent('u1', body(OFFLINE_EVENT_CAP + 1))).resolves.toBeDefined()
  }, 60_000)
})

describe('the pack', () => {
  it('is stored per user and flagged stale after 48 hours', async () => {
    const pack = apiPack([apiCard(1)])
    await eventStore.savePack('u1', pack, 1000)
    const row = (await eventStore.loadPack('u1'))!
    expect(row.pack.cards).toHaveLength(1)
    expect(await eventStore.loadPack('u2')).toBeUndefined()
    expect(isStale(row, 1000 + STALE_PACK_MS - 1)).toBe(false)
    expect(isStale(row, 1000 + STALE_PACK_MS + 1)).toBe(true)
  })

  it('shows cards reviewed on this device in their new state until a newer pack covers them', async () => {
    const card = apiCard(1)
    await eventStore.savePack('u1', apiPack([card]), 1000)
    await eventStore.addEvent('u1', body(1, { card_id: card.id }))
    await eventStore.saveLocalCard(
      'u1',
      card.id,
      { ...pick(card), state: 2, reps: 1, due_at: '2026-10-12T00:00:00Z' },
      2000,
    )
    expect((await eventStore.loadPack('u1'))!.pack.cards[0]!.reps).toBe(1)
    // A pack downloaded while the event is still waiting keeps the local state
    await eventStore.savePack('u1', apiPack([card], { generated_at: '2026-12-01T00:00:00Z' }), 3000)
    expect((await eventStore.loadPack('u1'))!.pack.cards[0]!.reps).toBe(1)
    // Once sent, the next pack replaces it
    await eventStore.removeEvents(['e-00001'])
    await eventStore.savePack('u1', apiPack([{ ...card, reps: 1 }], { generated_at: '2026-12-01T00:00:00Z' }), 4000)
    expect((await eventStore.loadPack('u1'))!.pack.cards[0]!.reps).toBe(1)
    expect((await eventStore.loadPack('u1'))!.pack.cards[0]!.state).toBe(0)
  })

  it('takes cards the server now holds back out of the pack when it answers about them', async () => {
    await eventStore.savePack('u1', apiPack([apiCard(1), apiCard(2)]))
    await eventStore.patchPack('u1', [
      {
        id: apiCard(1).id,
        rev: 2,
        state: 2,
        state_name: 'review',
        status: 'suspended',
        due_at: null,
        buried_until: null,
        reps: 3,
        lapses: 0,
        leech: false,
        needs_recheck: false,
      },
      {
        id: apiCard(2).id,
        rev: 2,
        state: 1,
        state_name: 'learning',
        status: 'active',
        due_at: '2026-10-09T09:00:00Z',
        buried_until: null,
        reps: 1,
        lapses: 0,
        leech: false,
        needs_recheck: false,
      },
    ])
    const cards = (await eventStore.loadPack('u1'))!.pack.cards
    expect(cards.map((c) => c.id)).toEqual([apiCard(2).id])
    expect(cards[0]!.rev).toBe(2)
    expect(cards[0]!.state).toBe(1)
  })
})

describe('sessions', () => {
  it('are kept per user', async () => {
    await eventStore.saveSession({
      id: 's1',
      userId: 'u1',
      source: 'today',
      startedAt: 1,
      plannedCount: 5,
      opened: false,
      closed: false,
      closeSent: false,
      summary: null,
    })
    expect((await eventStore.sessionsFor('u1')).map((s) => s.id)).toEqual(['s1'])
    expect(await eventStore.sessionsFor('u2')).toEqual([])
  })
})

function pick(c: ReturnType<typeof apiCard>) {
  return {
    state: c.state,
    stability: c.stability,
    difficulty: c.difficulty,
    due_scheduled_at: c.due_scheduled_at,
    postponed_until: c.postponed_until,
    due_at: c.due_at,
    last_review_at: c.last_review_at,
    reps: c.reps,
    lapses: c.lapses,
    step: c.step,
  }
}
