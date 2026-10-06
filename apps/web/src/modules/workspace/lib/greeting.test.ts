import { describe, expect, it } from 'vitest'

import type { CourseSummary } from '~/modules/personalization'

import { examChip, greetingFor, headline } from './greeting'

const course = (over: Partial<CourseSummary> = {}): CourseSummary => ({
  course: { code: 'cma', name: 'CMA' },
  level: { code: 'final', name: 'Final' },
  term: { code: '2027-06', name: 'June 2027' },
  exam_date: '2027-06-01',
  days_remaining: 238,
  daily_minutes: 120,
  ...over,
})

describe('greeting', () => {
  it.each([
    [0, 'Good morning'],
    [11, 'Good morning'],
    [12, 'Good afternoon'],
    [16, 'Good afternoon'],
    [17, 'Good evening'],
    [23, 'Good evening'],
  ])('hour %i is %s', (hour, expected) => expect(greetingFor(hour)).toBe(expected))

  it('adds the first name when there is one', () => {
    expect(headline(19, 'Aarav')).toBe('Good evening, Aarav')
    expect(headline(19, '')).toBe('Good evening')
  })
})

describe('examChip', () => {
  it('counts the days', () => {
    expect(examChip(course())).toEqual({ text: '238 days to CMA Final, June 2027', dated: true })
    expect(examChip(course({ days_remaining: 1 })).text).toBe('1 day to CMA Final, June 2027')
  })
  it('leaves out the attempt when there is none', () => {
    expect(examChip(course({ term: null })).text).toBe('238 days to CMA Final')
  })
  it('handles today and the past', () => {
    expect(examChip(course({ days_remaining: 0 })).text).toBe('CMA Final exam is today')
    expect(examChip(course({ days_remaining: -3 })).text).toBe('CMA Final exam date has passed')
  })
  it('nudges when the date or the course is missing', () => {
    expect(examChip(course({ exam_date: null, days_remaining: null }))).toEqual({
      text: 'Set your exam date',
      dated: false,
    })
    expect(examChip(null).dated).toBe(false)
  })
})
