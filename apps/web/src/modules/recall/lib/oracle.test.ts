/**
 * `ts-fsrs` as an oracle (D8): development only. With fuzz off our memory model must match it. Two documented differences
 * from py-fsrs, which is our authority (D7): ts-fsrs uses fractional elapsed days for retrievability (we floor to whole
 * days, as py-fsrs does), and counts calendar days rather than elapsed time for the same-day rule, so the histories here only use whole-day gaps or gaps of minutes; and it keeps Hard < Good < Easy at
 * least one day apart in the review phase, so review-phase due dates are compared to within two days.
 */

import { createEmptyCard, fsrs, generatorParameters, type Grade } from 'ts-fsrs'
import { describe, expect, it } from 'vitest'

import { type Cfg, DEFAULT_WEIGHTS, newMemoryState, review } from './fsrs6'

function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const pick = <T>(r: () => number, xs: readonly T[]): T => xs[Math.floor(r() * xs.length)]!
const unit = (m: number): `${number}m` => `${m}m`

describe('matches ts-fsrs with fuzz off', () => {
  it('on 2,000 random histories', () => {
    const r = rng(11)
    for (let h = 0; h < 2000; h++) {
      const steps = pick(r, [[1, 10], [1], [], [5, 15, 60]] as const)
      const rsteps = pick(r, [[10], [], [10, 30]] as const)
      const retention = pick(r, [0.85, 0.9, 0.93])
      const cap = pick(r, [365, 36500])
      const f = fsrs(
        generatorParameters({
          request_retention: retention,
          maximum_interval: cap,
          enable_fuzz: false,
          enable_short_term: true,
          learning_steps: steps.map(unit),
          relearning_steps: rsteps.map(unit),
          w: [...DEFAULT_WEIGHTS],
        }),
      )
      const cfg: Cfg = {
        desiredRetention: retention,
        learningSteps: steps,
        relearningSteps: rsteps,
        maxIntervalDays: cap,
        fuzz: false,
      }
      let t = new Date(Date.UTC(2026, 0, 1, 8))
      let card = createEmptyCard(t)
      let state = newMemoryState()
      const n = 1 + Math.floor(r() * 13)
      for (let i = 0; i < n; i++) {
        t = new Date(t.getTime() + pick(r, [1, 5, 30, 1440, 2880, 4320, 20160, 87840]) * 60_000)
        const rating = pick(r, [1, 2, 3, 3, 3, 4])
        card = f.next(card, t, rating as Grade).card
        const out = review(state, rating, t, DEFAULT_WEIGHTS, cfg, 'x')
        state = out.state
        const where = `history ${h}, review ${i}`
        expect(state.phase, where).toBe(card.state as number)
        expect(Math.abs(state.stability! - card.stability) / Math.max(1, card.stability), where).toBeLessThan(1e-6)
        expect(Math.abs(state.difficulty! - card.difficulty), where).toBeLessThan(1e-6)
        // Only review-phase due dates are compared: ts-fsrs keeps Hard < Good < Easy a day apart (so up to two days off),
        // and handles Hard and rounding of learning steps its own way. Learning steps are covered by the py-fsrs oracle and the vectors.
        if (state.phase === 2) {
          expect(Math.abs(out.dueAt.getTime() - card.due.getTime()), where).toBeLessThanOrEqual(2 * 86_400_000)
        }
      }
    }
  })
})
