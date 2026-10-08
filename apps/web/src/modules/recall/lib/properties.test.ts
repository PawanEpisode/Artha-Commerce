import { describe, expect, it } from 'vitest'

import { applyEvent, type CardEvent, fold, newCardState } from './folding'
import { type Cfg, DEFAULT_WEIGHTS, intervalDays, newMemoryState, retrievability, review } from './fsrs6'

const W = DEFAULT_WEIGHTS
const CFG: Cfg = {
  desiredRetention: 0.9,
  learningSteps: [1, 10],
  relearningSteps: [10],
  maxIntervalDays: 365,
  fuzz: true,
}
const T0 = Date.UTC(2026, 2, 2, 8)

/** Small seeded generator (mulberry32), so a failure reproduces. */
function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const pick = <T>(r: () => number, xs: readonly T[]): T => xs[Math.floor(r() * xs.length)]!

function history(r: () => number): CardEvent[] {
  const events: CardEvent[] = []
  let t = T0
  const n = 1 + Math.floor(r() * 12)
  for (let i = 0; i < n; i++) {
    t += (pick(r, [1, 5, 30, 600, 1440, 3000, 20000, 90000]) + i) * 60_000
    if (r() < 0.1) {
      events.push({
        type: 'schedule',
        id: `s${i}`,
        at: new Date(t),
        kind: pick(r, ['forget', 'content_reset', 'postpone', 'unpostpone']),
        toDue: new Date(t + 9 * 86_400_000),
        capDays: 3,
      })
    } else events.push({ type: 'review', id: `r${i}`, at: new Date(t), rating: pick(r, [1, 2, 3, 3, 4]) })
  }
  return events
}

const shuffle = <T>(r: () => number, xs: T[]): T[] => {
  const a = [...xs]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1))
    ;[a[i], a[j]] = [a[j]!, a[i]!]
  }
  return a
}

describe('replay properties', () => {
  it('fold ignores input order and duplicates', () => {
    const r = rng(1)
    for (let i = 0; i < 300; i++) {
      const events = history(r)
      const want = fold(events, W, CFG, 'c')
      const noisy = shuffle(r, [...events, ...events.slice(0, 3)])
      expect(fold(noisy, W, CFG, 'c')).toEqual(want)
    }
  })

  it('fold equals the incremental path', () => {
    const r = rng(2)
    const order = (e: CardEvent): number => (e.type === 'schedule' ? 0 : 1)
    for (let i = 0; i < 300; i++) {
      const events = history(r)
      let state = newCardState()
      const sorted = [...events].sort(
        (a, b) => a.at.getTime() - b.at.getTime() || order(a) - order(b) || a.id.localeCompare(b.id),
      )
      for (const e of sorted) state = applyEvent(state, e, W, CFG, 'c')
      expect(fold(events, W, CFG, 'c')).toEqual(state)
    }
  })

  it('voided reviews leave no trace', () => {
    const r = rng(3)
    for (let i = 0; i < 100; i++) {
      const events = history(r)
      const voided: CardEvent[] = events.map((e, k) => ({
        type: 'review',
        id: `v${k}`,
        at: new Date(e.at.getTime() + 1000),
        rating: 1,
        voided: true,
      }))
      expect(fold([...events, ...voided], W, CFG, 'c')).toEqual(fold(events, W, CFG, 'c'))
    }
  })
})

describe('scheduler properties', () => {
  it('a better rating never gives a shorter interval', () => {
    const cfg = { ...CFG, fuzz: false }
    for (const first of [1, 2, 3, 4]) {
      let s = review(newMemoryState(), first, new Date(T0), W, cfg, 'c').state
      s = review(s, 3, new Date(T0 + 60_000), W, cfg, 'c').state
      s = review(s, 3, new Date(T0 + 660_000), W, cfg, 'c').state
      for (const days of [1, 3, 10, 60, 400, 2000]) {
        const now = new Date(T0 + days * 86_400_000)
        const got = [1, 2, 3, 4].map((x) => review(s, x, now, W, cfg, 'c').scheduledDays)
        expect(got[1]!).toBeLessThanOrEqual(got[2]!)
        expect(got[2]!).toBeLessThanOrEqual(got[3]!)
        expect(got[0]!).toBeLessThanOrEqual(got[2]!)
      }
    }
  })

  it('retrievability falls with time and stays a probability; intervals are clamped', () => {
    const r = rng(4)
    for (let i = 0; i < 300; i++) {
      const s = 0.01 + r() * 3000
      const [a, b] = [r() * 4000, r() * 4000].sort((x, y) => x - y) as [number, number]
      const ra = retrievability(s, a, W[20]!)
      const rb = retrievability(s, b, W[20]!)
      expect(rb).toBeGreaterThan(0)
      expect(rb).toBeLessThanOrEqual(ra)
      expect(ra).toBeLessThanOrEqual(1)
      const n = intervalDays(s, 0.9, W[20]!, 365)
      expect(n).toBeGreaterThanOrEqual(1)
      expect(n).toBeLessThanOrEqual(365)
    }
  })
})
