import { describe, expect, it } from 'vitest'

import { COVER_WIDTH, coverScale, createLimiter, shouldGenerateCover } from './document-cover'

const ok = { status: 'ready', visible: true, online: true, needsFallback: true }

describe('shouldGenerateCover', () => {
  it('generates for a ready file that is on screen, online and has no server thumbnail', () => {
    expect(shouldGenerateCover(ok)).toBe(true)
  })

  it.each([
    ['locked', { status: 'needs_password' }],
    ['still preparing', { status: 'scanning' }],
    ['off screen', { visible: false }],
    ['offline', { online: false }],
    ['server thumbnail works', { needsFallback: false }],
  ])('does not generate when %s', (_name, change) => {
    expect(shouldGenerateCover({ ...ok, ...change })).toBe(false)
  })
})

describe('coverScale', () => {
  it('scales the page to the cover width', () => {
    expect(coverScale(595) * 595).toBeCloseTo(COVER_WIDTH)
  })
  it('falls back to 1 for a page without width', () => {
    expect(coverScale(0)).toBe(1)
  })
})

describe('createLimiter', () => {
  it('never runs more than max jobs at once and keeps the order', async () => {
    const limit = createLimiter(2)
    let running = 0
    let peak = 0
    const order: number[] = []
    const job = (n: number) => async () => {
      running += 1
      peak = Math.max(peak, running)
      order.push(n)
      await new Promise((r) => setTimeout(r, 5))
      running -= 1
      return n
    }
    const results = await Promise.all([1, 2, 3, 4, 5].map((n) => limit(job(n))))
    expect(results).toEqual([1, 2, 3, 4, 5])
    expect(order).toEqual([1, 2, 3, 4, 5])
    expect(peak).toBe(2)
  })

  it('keeps going after a job rejects', async () => {
    const limit = createLimiter(1)
    await expect(limit(() => Promise.reject(new Error('no')))).rejects.toThrow('no')
    await expect(limit(async () => 'fine')).resolves.toBe('fine')
  })
})
