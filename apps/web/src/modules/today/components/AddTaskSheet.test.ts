import { describe, expect, it } from 'vitest'

import { dateOf, validateAdd } from './AddTaskSheet'

const ok = { title: 'Call Sir', minutes: '20', when: 'today' as const, other: null }

describe('validateAdd', () => {
  it('accepts a good form', () => {
    expect(validateAdd(ok, '2026-10-14')).toEqual({})
  })
  it('needs a title of at most 120 characters', () => {
    expect(validateAdd({ ...ok, title: '  ' }, '2026-10-14').title).toBeTruthy()
    expect(validateAdd({ ...ok, title: 'x'.repeat(121) }, '2026-10-14').title).toBeTruthy()
    expect(validateAdd({ ...ok, title: 'x'.repeat(120) }, '2026-10-14').title).toBeUndefined()
  })
  it('needs whole minutes from 1 to 180', () => {
    for (const bad of ['0', '181', '2.5', '', 'abc'])
      expect(validateAdd({ ...ok, minutes: bad }, '2026-10-14').minutes).toBeTruthy()
    for (const good of ['1', '180']) expect(validateAdd({ ...ok, minutes: good }, '2026-10-14').minutes).toBeUndefined()
  })
  it('keeps the day within 30 days ahead', () => {
    const v = { ...ok, when: 'other' as const }
    expect(validateAdd({ ...v, other: null }, '2026-10-14').date).toBeTruthy()
    expect(validateAdd({ ...v, other: '2026-10-13' }, '2026-10-14').date).toBeTruthy()
    expect(validateAdd({ ...v, other: '2026-11-14' }, '2026-10-14').date).toBeTruthy()
    expect(validateAdd({ ...v, other: '2026-11-13' }, '2026-10-14').date).toBeUndefined()
  })
  it('turns the choice into a date', () => {
    expect(dateOf(ok, '2026-10-14')).toBe('2026-10-14')
    expect(dateOf({ ...ok, when: 'tomorrow' }, '2026-10-14')).toBe('2026-10-15')
    expect(dateOf({ ...ok, when: 'other', other: '2026-10-20' }, '2026-10-14')).toBe('2026-10-20')
  })
})
