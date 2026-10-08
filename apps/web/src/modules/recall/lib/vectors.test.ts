import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { type CardEvent, effectiveDue, fold } from './folding'
import {
  type Cfg,
  DEFAULT_WEIGHTS,
  formatInterval,
  fuzzUnit,
  type MemoryState,
  newMemoryState,
  review,
  SCHEDULER_VERSION,
} from './fsrs6'
import { type CardView, planQueue } from './queue'

const read = <T>(name: string): T =>
  JSON.parse(readFileSync(fileURLToPath(new URL(`./vectors/${name}`, import.meta.url)), 'utf8'))

interface StateJson {
  phase: number
  step: number | null
  stability: number | null
  difficulty: number | null
  last_review_at: string | null
  reps: number
  lapses: number
  last_lapse_at: string | null
}
interface CfgJson {
  desired_retention: number
  learning_steps: number[]
  relearning_steps: number[]
  max_interval_days: number
  fuzz: boolean
}
interface FsrsCase {
  name: string
  cfg: CfgJson
  weights: number[]
  card_id: string
  steps: {
    at: string
    rating: number
    state: StateJson
    scheduled_days: number
    due_at: string
    elapsed_days: number | null
    retrievability_before: number | null
    lapsed: boolean
  }[]
}
interface EventJson {
  type: 'review' | 'schedule'
  id: string
  at: string
  rating: number
  counts: boolean
  voided: boolean
  kind: string
  to_due: string | null
  cap_days: number | null
}
interface FoldCase {
  name: string
  cfg: CfgJson
  card_id: string
  events: EventJson[]
  expected: {
    memory: StateJson
    due_scheduled_at: string | null
    postponed_until: string | null
    effective_due: string | null
  }
}
interface QueueCase {
  name: string
  now: string
  w20: number
  mode: string
  day_end: string | null
  limits: { new_per_day: number; reviews_per_day: number; new_done_today?: number; reviews_done_today?: number }
  cards: {
    id: string
    subject: string
    importance: number
    phase: number
    stability: number | null
    last_review_at: string | null
    due_at: string | null
    created_at: string | null
  }[]
  expected: {
    ids: string[]
    learning: number
    reviews: number
    new: number
    catchup: { active: boolean; due_count: number; oldest_overdue_days: number; days_to_clear: number }
  }
}

const TOL = 1e-9
const d = (v: string | null): Date | null => (v === null ? null : new Date(v))
const close = (a: number | null, b: number | null): boolean =>
  a === null || b === null ? a === b : Math.abs(a - b) <= TOL * Math.max(1, Math.abs(b))

const cfgOf = (c: CfgJson): Cfg => ({
  desiredRetention: c.desired_retention,
  learningSteps: c.learning_steps,
  relearningSteps: c.relearning_steps,
  maxIntervalDays: c.max_interval_days,
  fuzz: c.fuzz,
})

function expectState(got: MemoryState, want: StateJson): void {
  expect(got.phase).toBe(want.phase)
  expect(got.step).toBe(want.step)
  expect(close(got.stability, want.stability)).toBe(true)
  expect(close(got.difficulty, want.difficulty)).toBe(true)
  expect(got.lastReviewAt?.getTime() ?? null).toBe(d(want.last_review_at)?.getTime() ?? null)
  expect([got.reps, got.lapses]).toEqual([want.reps, want.lapses])
  expect(got.lastLapseAt?.getTime() ?? null).toBe(d(want.last_lapse_at)?.getTime() ?? null)
}

describe('FSRS-6 golden vectors (shared with the Python domain)', () => {
  const fs = read<{
    scheduler_version: string
    cases: FsrsCase[]
    format_interval: [number, string][]
    fuzz_unit: [string, number, number][]
  }>('fsrs6_cases.json')
  it('is the same scheduler version with at least 40 cases', () => {
    expect(fs.scheduler_version).toBe(SCHEDULER_VERSION)
    expect(fs.cases.length).toBeGreaterThanOrEqual(40)
  })
  for (const c of fs.cases) {
    it(c.name, () => {
      const cfg = cfgOf(c.cfg)
      let state = newMemoryState()
      for (const step of c.steps) {
        const out = review(state, step.rating, new Date(step.at), c.weights, cfg, c.card_id)
        state = out.state
        expectState(state, step.state)
        expect(close(out.scheduledDays, step.scheduled_days)).toBe(true)
        expect(Math.abs(out.dueAt.getTime() - new Date(step.due_at).getTime())).toBeLessThanOrEqual(1)
        expect(out.elapsedDays).toBe(step.elapsed_days)
        expect(close(out.retrievabilityBefore, step.retrievability_before)).toBe(true)
        expect(out.lapsed).toBe(step.lapsed)
      }
    })
  }
  it('formats every interval label', () => {
    for (const [days, label] of fs.format_interval) expect(formatInterval(days), String(days)).toBe(label)
  })
  it('hashes every fuzz seed to the same unit', () => {
    for (const [cardId, reps, unit] of fs.fuzz_unit) expect(fuzzUnit(cardId, reps), `${cardId}:${reps}`).toBe(unit)
  })
})

describe('replay vectors', () => {
  for (const c of read<{ cases: FoldCase[] }>('folding_cases.json').cases) {
    it(c.name, () => {
      const events: CardEvent[] = c.events.map((e) =>
        e.type === 'review'
          ? {
              type: 'review',
              id: e.id,
              at: new Date(e.at),
              rating: e.rating,
              countsForScheduling: e.counts,
              voided: e.voided,
            }
          : { type: 'schedule', id: e.id, at: new Date(e.at), kind: e.kind, toDue: d(e.to_due), capDays: e.cap_days },
      )
      const state = fold(events, DEFAULT_WEIGHTS, cfgOf(c.cfg), c.card_id)
      expectState(state.memory, c.expected.memory)
      expect(state.dueScheduledAt?.getTime() ?? null).toBe(d(c.expected.due_scheduled_at)?.getTime() ?? null)
      expect(state.postponedUntil?.getTime() ?? null).toBe(d(c.expected.postponed_until)?.getTime() ?? null)
      expect(effectiveDue(state)?.getTime() ?? null).toBe(d(c.expected.effective_due)?.getTime() ?? null)
    })
  }
})

describe('queue vectors', () => {
  for (const c of read<{ cases: QueueCase[] }>('queue_cases.json').cases) {
    it(c.name, () => {
      const cards: CardView[] = c.cards.map((x) => ({
        id: x.id,
        subject: x.subject,
        importance: x.importance,
        phase: x.phase,
        stability: x.stability,
        lastReviewAt: d(x.last_review_at),
        dueAt: d(x.due_at),
        createdAt: d(x.created_at),
      }))
      const q = planQueue(
        cards,
        new Date(c.now),
        {
          newPerDay: c.limits.new_per_day,
          reviewsPerDay: c.limits.reviews_per_day,
          newDoneToday: c.limits.new_done_today,
          reviewsDoneToday: c.limits.reviews_done_today,
        },
        c.w20,
        { mode: c.mode, dayEnd: d(c.day_end) },
      )
      expect(q.ids).toEqual(c.expected.ids)
      expect([q.learning, q.reviews, q.new]).toEqual([c.expected.learning, c.expected.reviews, c.expected.new])
      expect({
        active: q.catchup.active,
        due_count: q.catchup.dueCount,
        oldest_overdue_days: q.catchup.oldestOverdueDays,
        days_to_clear: q.catchup.daysToClear,
      }).toEqual(c.expected.catchup)
    })
  }
})

describe('vector files', () => {
  it.each(['fsrs6_cases.json', 'folding_cases.json', 'queue_cases.json'])(
    '%s is byte for byte the API copy',
    (name) => {
      const web = readFileSync(fileURLToPath(new URL(`./vectors/${name}`, import.meta.url)))
      const api = readFileSync(
        fileURLToPath(new URL(`../../../../../api/modules/recall/domain/tests/vectors/${name}`, import.meta.url)),
      )
      expect(web.equals(api)).toBe(true)
    },
  )
})
