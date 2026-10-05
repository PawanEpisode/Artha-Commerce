import { describe, expect, it } from 'vitest'

import { AUTO_FLUSH_SECONDS, AUTO_GAP_MS, createAccumulator } from './autoCapture'

const T0 = Date.parse('2026-10-05T04:30:00Z')

describe('auto capture accumulator', () => {
  it('posts a chunk every five active minutes', () => {
    const acc = createAccumulator()
    let chunk = null
    for (let s = 1; s <= AUTO_FLUSH_SECONDS; s++) chunk = acc.tick(T0 + s * 1000, true)
    expect(chunk).toEqual({ started_at: new Date(T0).toISOString(), seconds: AUTO_FLUSH_SECONDS })
    expect(acc.pending()).toBe(0)
  })

  it('does not count time when the student is away', () => {
    const acc = createAccumulator()
    for (let s = 1; s <= 120; s++) acc.tick(T0 + s * 1000, s % 2 === 0)
    expect(acc.pending()).toBe(60)
  })

  it('keeps less than a minute to itself', () => {
    const acc = createAccumulator()
    for (let s = 1; s <= 59; s++) acc.tick(T0 + s * 1000, true)
    expect(acc.flush()).toBeNull()
    expect(acc.pending()).toBe(0)
  })

  it('hands over what is gathered when the tab hides', () => {
    const acc = createAccumulator()
    for (let s = 1; s <= 90; s++) acc.tick(T0 + s * 1000, true)
    expect(acc.flush()).toEqual({ started_at: new Date(T0).toISOString(), seconds: 90 })
    expect(acc.flush()).toBeNull()
  })

  it('starts a new chunk after a long gap instead of stretching over it', () => {
    const acc = createAccumulator()
    for (let s = 1; s <= 100; s++) acc.tick(T0 + s * 1000, true)
    const later = T0 + 100_000 + AUTO_GAP_MS + 1000
    const closed = acc.tick(later, true)
    expect(closed).toEqual({ started_at: new Date(T0).toISOString(), seconds: 100 })
    expect(acc.pending()).toBe(1)
  })
})
