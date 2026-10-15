import { describe, expect, it } from 'vitest'

import { bannerFor, cacheStatus, dateIn, dayRolledOver, STALE_AFTER_MS, updatedAgo } from './offline'

const IST = 'Asia/Kolkata'
// 2026-10-14 10:00 IST
const NOON = Date.parse('2026-10-14T04:30:00Z')

describe('dateIn', () => {
  it('reads the date in the student zone, not the device zone', () => {
    expect(dateIn(Date.parse('2026-10-13T20:00:00Z'), IST)).toBe('2026-10-14') // 01:30 IST next day
    expect(dateIn(Date.parse('2026-10-13T20:00:00Z'), 'UTC')).toBe('2026-10-13')
  })
  it('does not throw on an unknown zone', () => {
    expect(dateIn(NOON, 'Not/AZone')).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})

describe('cacheStatus (PRD 7.3: 6 hours, previous date)', () => {
  const entry = (savedAt: number, planDate = '2026-10-14') => ({ savedAt, planDate, tz: IST })
  it('is fresh under six hours on the same date', () => {
    expect(cacheStatus(entry(NOON - 3_600_000), NOON)).toBe('fresh')
    expect(cacheStatus(entry(NOON - STALE_AFTER_MS + 1), NOON)).toBe('fresh')
  })
  it('is stale from exactly six hours', () => {
    expect(cacheStatus(entry(NOON - STALE_AFTER_MS), NOON)).toBe('stale')
  })
  it('is a previous-day plan once the student date moved on, however recent the save', () => {
    const lateNight = Date.parse('2026-10-14T18:45:00Z') // 00:15 IST on the 15th
    expect(cacheStatus(entry(lateNight - 60_000), lateNight)).toBe('previous_day')
  })
})

describe('updatedAgo', () => {
  it('speaks minutes then hours', () => {
    expect(updatedAgo(NOON, NOON)).toBe('Updated just now')
    expect(updatedAgo(NOON - 5 * 60_000, NOON)).toBe('Updated 5 min ago')
    expect(updatedAgo(NOON - 7 * 3_600_000 - 600_000, NOON)).toBe('Updated 7 h ago')
  })
})

describe('dayRolledOver', () => {
  it('is true only after the local midnight of the plan date', () => {
    expect(dayRolledOver('2026-10-14', IST, NOON)).toBe(false)
    expect(dayRolledOver('2026-10-14', IST, Date.parse('2026-10-14T18:31:00Z'))).toBe(true)
  })
})

describe('bannerFor', () => {
  const base = { online: true, waiting: 0, cache: null, refreshing: false, now: NOON }
  it('shows nothing when online with a fresh plan', () => {
    expect(bannerFor(base)).toEqual({ kind: 'none' })
  })
  it('offline says how many changes wait', () => {
    expect(bannerFor({ ...base, online: false, waiting: 3 })).toEqual({ kind: 'offline', waiting: 3 })
  })
  it('back online with a queue says syncing', () => {
    expect(bannerFor({ ...base, waiting: 3 })).toEqual({ kind: 'syncing', waiting: 3 })
  })
  it('a stale cache offers a refresh and a refreshing cache says Updating', () => {
    const stale = { status: 'stale' as const, savedAt: NOON - 7 * 3_600_000 }
    expect(bannerFor({ ...base, cache: stale })).toEqual({ kind: 'stale', label: 'Updated 7 h ago' })
    expect(bannerFor({ ...base, cache: { status: 'fresh', savedAt: NOON }, refreshing: true })).toEqual({
      kind: 'updating',
    })
  })
  it('a plan of an earlier day wins over everything', () => {
    const old = { status: 'previous_day' as const, savedAt: NOON }
    expect(bannerFor({ ...base, online: false, waiting: 2, cache: old })).toEqual({ kind: 'previous_day' })
  })
})
