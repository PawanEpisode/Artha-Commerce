import { describe, expect, it } from 'vitest'

import { dueLabel } from './format'

const now = new Date(2026, 9, 16, 15, 0, 0)
const at = (day: number, hour = 9) => new Date(2026, 9, day, hour, 0, 0).toISOString()

describe('dueLabel', () => {
  it('has a dash when there is no due time', () => {
    expect(dueLabel(null, now)).toBe('-')
    expect(dueLabel(undefined, now)).toBe('-')
    expect(dueLabel('not a date', now)).toBe('-')
  })

  it('counts calendar days, not 24-hour blocks', () => {
    expect(dueLabel(at(16, 8), now)).toBe('Today')
    expect(dueLabel(at(16, 23), now)).toBe('Today')
    expect(dueLabel(at(17, 1), now)).toBe('Tomorrow')
    expect(dueLabel(at(20), now)).toBe('In 4 d')
  })

  it('says how late an overdue card is', () => {
    expect(dueLabel(at(15), now)).toBe('1 d overdue')
    expect(dueLabel(at(10), now)).toBe('6 d overdue')
  })

  it('gives a date from two weeks out', () => {
    expect(dueLabel(new Date(2026, 10, 20, 9).toISOString(), now)).toMatch(/20/)
  })
})
