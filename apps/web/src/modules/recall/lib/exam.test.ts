/* eslint-disable @typescript-eslint/no-explicit-any -- the shared JSON vectors are read untyped; their shape is checked by the assertions */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { cfgAt, cramOpen, horizon, pacing, type QuickCard, quickSet, retentionFor, rExam, slotOf } from './exam'
import { fold } from './folding'
import { effectiveDue } from './folding'
import { DEFAULT_CFG, DEFAULT_WEIGHTS } from './fsrs6'

const data = JSON.parse(
  readFileSync(fileURLToPath(new URL('./vectors/exam_cases.json', import.meta.url)), 'utf8'),
) as Record<string, any[]>

const d = (v: string | null): Date | null => (v === null ? null : new Date(v))
const same = (a: Date | null, b: Date | null): boolean =>
  a === null || b === null ? a === b : a.getTime() === b.getTime()
const close = (a: number, b: number): boolean => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b))

describe('exam vectors (shared with the Python domain)', () => {
  it('has the cases', () => {
    expect(Object.values(data).reduce((n, v) => n + v.length, 0)).toBeGreaterThanOrEqual(400)
  })
  it('horizon', () => {
    for (const c of data.horizon!) {
      const got = horizon(d(c.due), d(c.last_review), d(c.exam), c.card_id, d(c.now)!, c.enabled)
      expect(same(got, d(c.expected)), c.name).toBe(true)
    }
  })
  it('retention', () => {
    for (const c of data.retention!) expect(retentionFor(c.importance, c.desired, c.left, c.enabled)).toBe(c.expected)
  })
  it('r_exam', () => {
    for (const c of data.r_exam!) {
      const got = rExam(c.stability, d(c.last_review), d(c.exam)!, c.w20)
      if (c.expected === null) expect(got).toBeNull()
      else expect(close(got!, c.expected)).toBe(true)
    }
  })
  it('quick set', () => {
    for (const c of data.quick!) {
      const cards: QuickCard[] = c.cards.map((x: any) => ({
        id: x.id,
        importance: x.importance,
        phase: x.phase,
        stability: x.stability,
        lastReviewAt: d(x.last_review),
      }))
      const p = quickSet(cards, d(c.exam)!, c.minutes, c.median, d(c.now)!, c.w20)
      expect(p.ids, c.name).toEqual(c.expected.ids)
      expect([p.candidates, p.cutOff, p.daysToExam, p.windowDays, p.perDay, p.minutesPerDay, p.tooFew]).toEqual([
        c.expected.candidates,
        c.expected.cut_off,
        c.expected.days_to_exam,
        c.expected.window_days,
        c.expected.per_day,
        c.expected.minutes_per_day,
        c.expected.too_few,
      ])
    }
  })
  it('cram window', () => {
    for (const c of data.cram!) expect(cramOpen(d(c.now)!, d(c.exam))).toBe(c.expected)
  })
  it('pacing', () => {
    for (const c of data.pacing!) {
      const p = pacing(c.unseen, c.days_left, c.new_per_day)
      expect([p.unseen, p.windowDays, p.introducedAtLimit, p.neededPerDay, p.feasible]).toEqual([
        c.expected.unseen,
        c.expected.window_days,
        c.expected.introduced_at_limit,
        c.expected.needed_per_day,
        c.expected.feasible,
      ])
    }
  })
  it('a fold with the retention boost', () => {
    for (const c of data.fold_boost!) {
      const cfg = { ...DEFAULT_CFG, fuzz: true }
      const events = c.events.map((e: any) => ({
        type: 'review' as const,
        id: e.id,
        at: new Date(e.at),
        rating: e.rating,
      }))
      const state = fold(events, DEFAULT_WEIGHTS, cfg, c.card_id, (at) => cfgAt(cfg, c.importance, at, d(c.exam)))
      expect(state.memory.reps, c.name).toBe(c.expected.reps)
      expect(close(state.memory.stability!, c.expected.stability), c.name).toBe(true)
      expect(same(effectiveDue(state), d(c.expected.effective_due)), c.name).toBe(true)
    }
  })
})

describe('slotOf', () => {
  it('is the first eight hex digits modulo five', () => {
    expect(slotOf('ffffffff-0000-4000-8000-000000000000')).toBe(0)
    expect(slotOf('00000003-0000-4000-8000-000000000000')).toBe(3)
  })
})
