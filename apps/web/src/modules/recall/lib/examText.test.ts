import { describe, expect, it } from 'vitest'

import { countdown, cutOffSentence, pacingMessage, quickSummary } from './examText'

const pacing = (o: Partial<Parameters<typeof pacingMessage>[0]> = {}) => ({
  unseen: 100,
  window_days: 46,
  new_per_day: 10,
  introduced_at_limit: 100,
  needed_per_day: 3,
  feasible: true,
  ...o,
})

describe('exam sentences', () => {
  it('counts whole days and names the last two', () => {
    expect(countdown(36.4, false)).toBe('36 days to your exam')
    expect(countdown(1.2, false)).toBe('Your exam is tomorrow')
    expect(countdown(0.4, false)).toBe('Your exam is today')
    expect(countdown(0.4, true)).toBe('Your exam is within a day')
  })
  it('says the arithmetic of pacing without blame', () => {
    expect(pacingMessage(pacing())).toContain('seen them all')
    const short = pacingMessage(pacing({ new_per_day: 2, introduced_at_limit: 92, needed_per_day: 3, feasible: false }))
    expect(short).toContain('92 of them')
    expect(short).toContain('Raise new cards to 3 a day')
    expect(pacingMessage(pacing({ unseen: 0 }))).toContain('seen at least once')
    expect(pacingMessage(pacing({ window_days: 0, feasible: false }))).toContain('window has closed')
  })
  it('summarises the plan and what is left out', () => {
    expect(quickSummary({ selected: 1, window_days: 1, per_day: 1, minutes_per_day: 1 })).toContain('1 card over 1 day')
    expect(quickSummary({ selected: 0, window_days: 5, per_day: 0, minutes_per_day: 0 })).toBe(
      'Nothing needs quick revision.',
    )
    expect(cutOffSentence(0)).toBeNull()
    expect(cutOffSentence(3)).toContain('3 cards did not fit')
  })
})
