import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { celebrationMessage, celebrationSeen, markCelebrated } from './celebration'
import type { CourseSummary } from './types'

const course = (over: Partial<CourseSummary> = {}): CourseSummary => ({
  course: { code: 'cma', name: 'CMA' },
  level: { code: 'final', name: 'Final' },
  term: { code: '2027-06', name: 'June 2027' },
  exam_date: '2027-06-01',
  days_remaining: 238,
  daily_minutes: 180,
  ...over,
})

describe('celebrationMessage', () => {
  it('names the course, attempt and days to go', () => {
    expect(celebrationMessage('Aarav', course())).toBe('Aarav, CMA Final June 2027 is set up. 238 days to go.')
  })
  it('leaves out what is not known', () => {
    expect(celebrationMessage('Aarav', course({ term: null, days_remaining: null }))).toBe(
      'Aarav, CMA Final is set up.',
    )
    expect(celebrationMessage('', course({ days_remaining: 1 }))).toBe('CMA Final June 2027 is set up. 1 day to go.')
    expect(celebrationMessage('Aarav', course({ days_remaining: 0 }))).toBe('Aarav, CMA Final June 2027 is set up.')
  })
  it('works without a course', () => {
    expect(celebrationMessage('Aarav', null)).toBe('Aarav, your workspace is ready.')
    expect(celebrationMessage('', null)).toBe('Your workspace is ready.')
  })
})

describe('celebrationSeen', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    })
  })
  afterEach(() => vi.unstubAllGlobals())
  it('is per version', () => {
    expect(celebrationSeen(2)).toBe(false)
    markCelebrated(2)
    expect(celebrationSeen(2)).toBe(true)
    expect(celebrationSeen(3)).toBe(false)
  })
})
