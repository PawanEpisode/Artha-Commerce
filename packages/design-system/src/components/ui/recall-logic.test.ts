import { describe, expect, it } from 'vitest'

import { addIsoDays, clampIsoDate, isIsoDate, todayIsoDate } from './date-picker'
import { swipeDirection } from './flip-card'
import { counterText } from './progress-counter'
import { ratingForKey, rovingIndex } from './rating-buttons'

describe('ratingForKey', () => {
  it('maps 1 to 4 and nothing else', () => {
    expect([1, 2, 3, 4].map((n) => ratingForKey(String(n)))).toEqual([1, 2, 3, 4])
    for (const k of ['0', '5', 'a', ' ', 'Enter', '']) expect(ratingForKey(k)).toBeNull()
  })
})

describe('rovingIndex', () => {
  it('moves one step and stops at the ends', () => {
    expect(rovingIndex(1, 'ArrowRight', 4)).toBe(2)
    expect(rovingIndex(3, 'ArrowRight', 4)).toBe(3)
    expect(rovingIndex(0, 'ArrowLeft', 4)).toBe(0)
    expect(rovingIndex(2, 'ArrowUp', 4)).toBe(1)
    expect(rovingIndex(2, 'ArrowDown', 4)).toBe(3)
  })
  it('jumps with Home and End and ignores other keys', () => {
    expect(rovingIndex(2, 'Home', 4)).toBe(0)
    expect(rovingIndex(0, 'End', 4)).toBe(3)
    expect(rovingIndex(2, 'Tab', 4)).toBeNull()
    expect(rovingIndex(0, 'ArrowRight', 0)).toBeNull()
  })
})

describe('swipeDirection', () => {
  it('needs a long, mostly horizontal move', () => {
    expect(swipeDirection(-100, 5)).toBe('left')
    expect(swipeDirection(100, -5)).toBe('right')
    expect(swipeDirection(30, 0)).toBeNull()
    expect(swipeDirection(100, 100)).toBeNull()
    expect(swipeDirection(10, 120)).toBeNull()
  })
})

describe('counterText', () => {
  it('keeps the numbers inside their range', () => {
    expect(counterText(12, 30)).toBe('12 of 30')
    expect(counterText(40, 30)).toBe('30 of 30')
    expect(counterText(-3, 30)).toBe('0 of 30')
    expect(counterText(0, 0)).toBe('No cards')
    expect(counterText(Number.NaN, Number.NaN)).toBe('No cards')
  })
})

describe('date helpers', () => {
  it('recognises real calendar days only', () => {
    expect(isIsoDate('2026-10-09')).toBe(true)
    expect(isIsoDate('2026-02-30')).toBe(false)
    expect(isIsoDate('09/10/2026')).toBe(false)
    expect(isIsoDate('')).toBe(false)
  })
  it('clamps to min and max', () => {
    expect(clampIsoDate('2026-10-01', '2026-10-09', '2026-12-01')).toBe('2026-10-09')
    expect(clampIsoDate('2027-01-01', '2026-10-09', '2026-12-01')).toBe('2026-12-01')
    expect(clampIsoDate('2026-11-01', '2026-10-09', '2026-12-01')).toBe('2026-11-01')
    expect(clampIsoDate('2026-11-01')).toBe('2026-11-01')
  })
  it('adds days across month ends and formats today in local time', () => {
    expect(addIsoDays('2026-10-30', 3)).toBe('2026-11-02')
    expect(addIsoDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(todayIsoDate(new Date(2026, 9, 9, 23, 59))).toBe('2026-10-09')
  })
})
