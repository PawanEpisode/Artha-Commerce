import { describe, expect, it } from 'vitest'

import { clampMinutes, formatDuration, joinMinutes, parseDurationPart, splitMinutes } from './duration'

describe('splitMinutes', () => {
  it('splits into hours and minutes', () => {
    expect(splitMinutes(90)).toEqual({ hours: 1, minutes: 30 })
    expect(splitMinutes(60)).toEqual({ hours: 1, minutes: 0 })
    expect(splitMinutes(59)).toEqual({ hours: 0, minutes: 59 })
  })
  it('handles zero, negative and NaN as zero', () => {
    expect(splitMinutes(0)).toEqual({ hours: 0, minutes: 0 })
    expect(splitMinutes(-5)).toEqual({ hours: 0, minutes: 0 })
    expect(splitMinutes(Number.NaN)).toEqual({ hours: 0, minutes: 0 })
    expect(splitMinutes(Number.POSITIVE_INFINITY)).toEqual({ hours: 0, minutes: 0 })
  })
  it('allows more than 24 hours and rounds fractions', () => {
    expect(splitMinutes(26 * 60 + 5)).toEqual({ hours: 26, minutes: 5 })
    expect(splitMinutes(89.6)).toEqual({ hours: 1, minutes: 30 })
  })
})

describe('joinMinutes', () => {
  it('rolls minutes over', () => {
    expect(joinMinutes(0, 75)).toBe(75)
    expect(splitMinutes(joinMinutes(0, 75))).toEqual({ hours: 1, minutes: 15 })
    expect(joinMinutes(1, 30)).toBe(90)
  })
  it('treats invalid parts as zero', () => {
    expect(joinMinutes(Number.NaN, 10)).toBe(10)
    expect(joinMinutes(-1, -1)).toBe(0)
  })
})

describe('clampMinutes', () => {
  it('caps at max and floors at zero', () => {
    expect(clampMinutes(500, 480)).toBe(480)
    expect(clampMinutes(-3, 480)).toBe(0)
    expect(clampMinutes(30)).toBe(30)
  })
})

describe('formatDuration', () => {
  it('formats short', () => {
    expect(formatDuration(90)).toBe('1 h 30 m')
    expect(formatDuration(120)).toBe('2 h')
    expect(formatDuration(45)).toBe('45 m')
    expect(formatDuration(0)).toBe('0 m')
    expect(formatDuration(Number.NaN)).toBe('0 m')
  })
  it('formats long with plurals', () => {
    expect(formatDuration(61, 'long')).toBe('1 hour 1 minute')
    expect(formatDuration(150, 'long')).toBe('2 hours 30 minutes')
    expect(formatDuration(0, 'long')).toBe('0 minutes')
    expect(formatDuration(25 * 60, 'long')).toBe('25 hours')
  })
})

describe('parseDurationPart', () => {
  it('parses typed text', () => {
    expect(parseDurationPart('')).toBeNull()
    expect(parseDurationPart('  ')).toBeNull()
    expect(parseDurationPart('12')).toBe(12)
    expect(parseDurationPart('1.9')).toBe(1)
    expect(parseDurationPart('-4')).toBeNull()
    expect(parseDurationPart('abc')).toBeNull()
  })
})
