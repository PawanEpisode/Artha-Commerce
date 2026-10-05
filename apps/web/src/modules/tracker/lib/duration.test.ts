import { describe, expect, it } from 'vitest'

import {
  addDays,
  daysBetween,
  elapsedSeconds,
  formatClock,
  formatDuration,
  fromLocalInput,
  localDate,
  spokenDuration,
  toLocalInput,
  weekdayOf,
  weekStartOf,
} from './duration'

describe('formatDuration', () => {
  it('floors to minutes and drops hours when there are none', () => {
    expect(formatDuration(0)).toBe('0 m')
    expect(formatDuration(59)).toBe('0 m')
    expect(formatDuration(45 * 60)).toBe('45 m')
    expect(formatDuration(3600)).toBe('1 h')
    expect(formatDuration(3600 + 5 * 60 + 59)).toBe('1 h 5 m')
  })
  it('never shows a negative time', () => {
    expect(formatDuration(-5)).toBe('0 m')
  })
})

describe('spokenDuration', () => {
  it('uses words and the right plural', () => {
    expect(spokenDuration(3600 + 60)).toBe('1 hour 1 minute')
    expect(spokenDuration(2 * 3600 + 5 * 60)).toBe('2 hours 5 minutes')
    expect(spokenDuration(0)).toBe('0 minutes')
  })
})

describe('formatClock', () => {
  it('pads hours, minutes and seconds', () => {
    expect(formatClock(0)).toBe('00:00:00')
    expect(formatClock(3661)).toBe('01:01:01')
  })
})

describe('elapsedSeconds', () => {
  const base = { started_at: '2026-10-05T04:00:00Z', paused_at: null, paused_total_seconds: 0 }
  const at = (iso: string) => Date.parse(iso)
  it('counts wall time while running, minus finished pauses', () => {
    expect(elapsedSeconds({ ...base, status: 'running' }, at('2026-10-05T04:30:00Z'))).toBe(1800)
    expect(elapsedSeconds({ ...base, status: 'running', paused_total_seconds: 300 }, at('2026-10-05T04:30:00Z'))).toBe(
      1500,
    )
  })
  it('stops counting at the pause', () => {
    const paused = { ...base, status: 'paused' as const, paused_at: '2026-10-05T04:10:00Z' }
    expect(elapsedSeconds(paused, at('2026-10-05T09:00:00Z'))).toBe(600)
  })
  it('is never negative', () => {
    expect(elapsedSeconds({ ...base, status: 'running' }, at('2026-10-05T03:00:00Z'))).toBe(0)
  })
})

describe('dates', () => {
  it('works out the local calendar date in a time zone', () => {
    // 20:00 UTC on the 5th is 01:30 on the 6th in India.
    expect(localDate(Date.parse('2026-10-05T20:00:00Z'), 'Asia/Kolkata')).toBe('2026-10-06')
    expect(localDate(Date.parse('2026-10-05T20:00:00Z'), 'UTC')).toBe('2026-10-05')
  })
  it('adds days across month ends', () => {
    expect(addDays('2026-09-30', 1)).toBe('2026-10-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(daysBetween('2026-10-01', '2026-10-05')).toBe(4)
  })
  it('finds the first day of the week for both week starts', () => {
    expect(weekdayOf('2026-10-05')).toBe(0) // Monday
    expect(weekStartOf('2026-10-08', 1)).toBe('2026-10-05')
    expect(weekStartOf('2026-10-08', 0)).toBe('2026-10-04')
    expect(weekStartOf('2026-10-04', 0)).toBe('2026-10-04')
    expect(weekStartOf('2026-10-04', 1)).toBe('2026-09-28')
  })
})

describe('datetime-local conversion', () => {
  it('round-trips an instant through a zone', () => {
    const instant = Date.parse('2026-10-05T04:30:00Z')
    const shown = toLocalInput(instant, 'Asia/Kolkata')
    expect(shown).toBe('2026-10-05T10:00')
    expect(fromLocalInput(shown, 'Asia/Kolkata').getTime()).toBe(instant)
  })
  it('reads wall-clock time across a daylight saving change', () => {
    const shown = '2026-03-29T12:00'
    const instant = fromLocalInput(shown, 'Europe/London')
    expect(toLocalInput(instant, 'Europe/London')).toBe(shown)
  })
})
