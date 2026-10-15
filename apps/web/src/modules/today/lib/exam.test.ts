import { describe, expect, it } from 'vitest'

import { daysBetween, examDateError, shouldOfferExamCard, upcomingTerms } from './exam'

const term = (id: string, exam_start: string | null) => ({ id, name: id, exam_start })

describe('upcomingTerms', () => {
  it('drops past terms, sorts soonest first, puts undated last and caps the list', () => {
    const terms = [
      term('may27', '2027-05-10'),
      term('old', '2026-05-01'),
      term('nov26', '2026-11-05'),
      term('none', null),
      term('jan27', '2027-01-12'),
      term('sep27', '2027-09-01'),
      term('may28', '2028-05-01'),
    ]
    expect(upcomingTerms(terms, '2026-10-14').map((t) => t.id)).toEqual(['nov26', 'jan27', 'may27', 'sep27'])
    expect(upcomingTerms([term('none', null), term('nov26', '2026-11-05')], '2026-10-14').map((t) => t.id)).toEqual([
      'nov26',
      'none',
    ])
  })
})

describe('examDateError', () => {
  it('accepts a real date after today', () => {
    expect(examDateError('2026-11-05', '2026-10-14')).toBeNull()
  })
  it('refuses empty, impossible, today and past dates', () => {
    expect(examDateError('', '2026-10-14')).toBe('Pick a date.')
    expect(examDateError('2026-02-30', '2026-10-14')).toBe('That date does not exist.')
    expect(examDateError('2026-10-14', '2026-10-14')).toBe('Pick a date after today.')
    expect(examDateError('2026-10-01', '2026-10-14')).toBe('Pick a date after today.')
  })
})

describe('daysBetween and shouldOfferExamCard', () => {
  it('counts calendar days across a month end', () => {
    expect(daysBetween('2026-10-14', '2026-11-05')).toBe(22)
  })
  it('offers the card only with no exam date and not dismissed', () => {
    expect(shouldOfferExamCard(null, false)).toBe(true)
    expect(shouldOfferExamCard(null, true)).toBe(false)
    expect(shouldOfferExamCard(30, false)).toBe(false)
  })
})
