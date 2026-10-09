import { describe, expect, it } from 'vitest'

import { fold, type ReviewEvent } from './folding'
import { DEFAULT_WEIGHTS } from './fsrs6'
import {
  aheadFromPack,
  answer,
  currentCard,
  doneCount,
  drop,
  extend,
  isFinished,
  planFromPack,
  playerCardOf,
  type PlayerState,
  previewLabels,
  type Rating,
  schedulerOf,
  startPlayer,
  undo,
} from './player'
import { apiCard, apiPack, rng, SETTINGS } from './testing'

const sched = schedulerOf(SETTINGS, DEFAULT_WEIGHTS)
const NOW = new Date('2026-10-09T08:00:00Z')

let counter = 0
const ctx = (now: Date) => ({
  now,
  durationMs: 4000,
  sessionId: 'sess',
  deviceId: 'dev',
  newId: () => `evt-${++counter}`,
  tzOffsetMin: 330,
  sched,
})

describe('an offline session of 100 cards', () => {
  it('ends on the same memory as the server fold of the same events', () => {
    const cards = Array.from({ length: 100 }, (_, i) => playerCardOf(apiCard(i + 1)))
    const random = rng(7)
    let s: PlayerState = startPlayer(cards)
    const events: { cardId: string; event: ReviewEvent }[] = []
    let t = NOW.getTime()
    let guard = 0
    while (!isFinished(s) && guard++ < 1000) {
      t += 30_000
      const rating = (1 + Math.floor(random() * 4)) as Rating
      const out = answer(s, rating, ctx(new Date(t)))!
      events.push({
        cardId: out.event.card_id,
        event: { type: 'review', id: out.event.id, at: new Date(out.event.reviewed_at), rating },
      })
      s = out.state
    }
    expect(isFinished(s)).toBe(true)
    expect(guard).toBeLessThan(1000)
    for (const card of cards) {
      const mine = events.filter((e) => e.cardId === card.id).map((e) => e.event)
      const server = fold(mine, DEFAULT_WEIGHTS, sched.cfg, card.id)
      const local = s.cards[card.id]!
      expect(local.memory.reps).toBe(server.memory.reps)
      expect(local.memory.lapses).toBe(server.memory.lapses)
      expect(local.memory.stability).toBe(server.memory.stability)
      expect(local.memory.difficulty).toBe(server.memory.difficulty)
      expect(local.dueScheduledAt?.getTime()).toBe(server.dueScheduledAt?.getTime())
    }
    expect(doneCount(s)).toBe(100)
  })
})

describe('the queue while playing', () => {
  const three = () => startPlayer([1, 2, 3, 4, 5].map((i) => playerCardOf(apiCard(i))))

  it('sends an Again card back a few cards later and keeps the count of finished cards honest', () => {
    const s = three()
    const first = currentCard(s)!
    const out = answer(s, 1, ctx(NOW))!
    expect(out.state.queue).toHaveLength(5)
    expect(out.state.queue[0]).not.toBe(first.id)
    expect(out.state.queue).toContain(first.id)
    expect(doneCount(out.state)).toBe(0)
    expect(out.state.total).toBe(5)
  })

  it('finishes a card that graduates beyond the session', () => {
    let s = three()
    for (const rating of [4, 4, 4, 4, 4] as Rating[]) s = answer(s, rating, ctx(NOW))!.state
    expect(isFinished(s)).toBe(true)
    expect(doneCount(s)).toBe(5)
  })

  it('builds an event that carries ids and timing only, never card text', () => {
    const { event } = answer(three(), 3, ctx(NOW))!
    expect(Object.keys(event).sort()).toEqual(
      [
        'card_id',
        'device_id',
        'duration_ms',
        'id',
        'item_version_id',
        'mode',
        'rating',
        'reviewed_at',
        'session_id',
        'tz_offset_min',
      ].sort(),
    )
    expect(JSON.stringify(event)).not.toContain('Question')
    expect(event.reviewed_at).toBe(NOW.toISOString())
    expect(event.tz_offset_min).toBe(330)
  })

  it('caps a very long think time at the server limit', () => {
    const { event } = answer(three(), 3, { ...ctx(NOW), durationMs: 5_000_000 })!
    expect(event.duration_ms).toBe(600_000)
  })

  it('undoes the last answers, restoring the card, the queue and the counters', () => {
    let s = three()
    const before = s
    s = answer(s, 3, ctx(NOW))!.state
    s = answer(s, 1, ctx(NOW))!.state
    const first = undo(s, new Date(NOW.getTime() + 1000))!
    const second = undo(first.state, new Date(NOW.getTime() + 2000))!
    expect(second.state.queue).toEqual(before.queue)
    expect(second.state.cards).toEqual(before.cards)
    expect(second.state.answered).toBe(0)
    expect(second.state.ratings).toEqual({ again: 0, hard: 0, good: 0, easy: 0 })
    expect(undo(second.state, NOW)).toBeNull()
  })

  it('refuses an undo after 30 minutes and keeps only the last 10 answers', () => {
    let s = three()
    s = answer(s, 3, ctx(NOW))!.state
    expect(undo(s, new Date(NOW.getTime() + 31 * 60_000))).toBeNull()
    let long = startPlayer(Array.from({ length: 15 }, (_, i) => playerCardOf(apiCard(i + 1))))
    for (let i = 0; i < 15; i++) long = answer(long, 4, ctx(NOW))!.state
    expect(long.history).toHaveLength(10)
  })

  it('drops a held card and adds review-ahead cards without repeating any', () => {
    let s = three()
    const first = currentCard(s)!.id
    s = drop(s, first)
    expect(s.queue).not.toContain(first)
    expect(s.total).toBe(4)
    const extra = [playerCardOf(apiCard(2)), playerCardOf(apiCard(9), 'review_ahead')]
    const grown = extend(s, extra)
    expect(grown.queue.filter((id) => id === extra[0]!.id)).toHaveLength(1)
    expect(grown.total).toBe(5)
  })

  it('shows the interval each answer would give, from the same scheduler', () => {
    const labels = previewLabels(currentCard(three())!, NOW, sched)
    expect(labels[1]).toBe('1 min')
    expect(labels[2]).toMatch(/min$/)
    expect(Object.values(labels).every((l) => l.length > 0)).toBe(true)
  })
})

describe('planning from a stored pack', () => {
  const due = (i: number, hoursAgo: number) =>
    apiCard(i, {
      state: 2,
      stability: 5,
      difficulty: 5,
      last_review_at: new Date(NOW.getTime() - 5 * 86_400_000).toISOString(),
      due_scheduled_at: new Date(NOW.getTime() - hoursAgo * 3_600_000).toISOString(),
      due_at: new Date(NOW.getTime() - hoursAgo * 3_600_000).toISOString(),
      reps: 3,
    })

  it('puts due reviews first and respects the daily new-card limit', () => {
    const cards = [due(1, 5), due(2, 2), ...[3, 4, 5, 6].map((i) => apiCard(i))]
    const pack = apiPack(cards, {
      settings: { ...SETTINGS, new_per_day: 2 },
      counters: { new_done_today: 1, reviews_done_today: 0, local_date: '2026-10-09' },
    })
    const plan = planFromPack(pack, NOW)
    expect(plan.cards).toHaveLength(3)
    expect(plan.cards.slice(0, 2).every((c) => c.memory.phase === 2)).toBe(true)
    expect(plan.cards.filter((c) => c.wasNew)).toHaveLength(1)
  })

  it('goes into catch-up when the backlog is far over the limit and adds no new cards', () => {
    const cards = [...Array.from({ length: 12 }, (_, i) => due(i + 1, 24 * 4)), apiCard(50)]
    const pack = apiPack(cards, { settings: { ...SETTINGS, reviews_per_day: 5 } })
    const plan = planFromPack(pack, NOW)
    expect(plan.catchup.active).toBe(true)
    expect(plan.mode).toBe('catchup')
    expect(plan.cards.some((c) => c.wasNew)).toBe(false)
    expect(plan.cards.every((c) => c.mode === 'catchup')).toBe(true)
  })

  it('picks the weakest cards due later for "Review ahead"', () => {
    const later = (i: number, days: number) =>
      apiCard(i, {
        state: 2,
        stability: 10,
        difficulty: 5,
        last_review_at: new Date(NOW.getTime() - 3 * 86_400_000).toISOString(),
        due_at: new Date(NOW.getTime() + days * 86_400_000).toISOString(),
        due_scheduled_at: new Date(NOW.getTime() + days * 86_400_000).toISOString(),
      })
    const pack = apiPack([later(1, 2), later(2, 5), apiCard(3), due(4, 1)])
    const ahead = aheadFromPack(pack, NOW, new Set(), 10)
    expect(ahead.map((c) => c.id)).toHaveLength(2)
    expect(ahead.every((c) => c.mode === 'review_ahead')).toBe(true)
    expect(aheadFromPack(pack, NOW, new Set([ahead[0]!.id]), 10)).toHaveLength(1)
  })
})
