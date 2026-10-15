import { describe, expect, it } from 'vitest'

import { dayPart, examCountdown, formatDay, formatMinutes, greeting, hourIn } from './time'

describe('time helpers', () => {
  it('reads the hour in the student zone', () => {
    expect(hourIn('2026-10-14T18:30:00Z', 'Asia/Kolkata')).toBe(0)
    expect(hourIn('2026-10-14T03:00:00Z', 'Asia/Kolkata')).toBe(8)
    expect(hourIn('nonsense', 'Asia/Kolkata')).toBe(12)
  })
  it('names the part of day', () => {
    expect([dayPart(5), dayPart(12), dayPart(16), dayPart(17), dayPart(23)]).toEqual([
      'morning',
      'afternoon',
      'afternoon',
      'evening',
      'evening',
    ])
    expect(greeting('morning', 'Aarav')).toBe('Good morning, Aarav')
    expect(greeting('evening')).toBe('Good evening')
  })
  it('formats minutes and days', () => {
    expect(formatMinutes(0)).toBe('0 min')
    expect(formatMinutes(45)).toBe('45 min')
    expect(formatMinutes(60)).toBe('1 h')
    expect(formatMinutes(95)).toBe('1 h 35 min')
    expect(formatDay('2026-10-14')).toBe('Wed 14 Oct')
    expect(examCountdown(238)).toBe('238 days to your exam')
    expect(examCountdown(1)).toBe('1 day to your exam')
    expect(examCountdown(0)).toBe('Exam day')
    expect(examCountdown(null)).toBeNull()
  })
})
