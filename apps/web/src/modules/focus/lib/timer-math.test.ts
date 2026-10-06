import { describe, expect, it } from 'vitest'

import {
  elapsedSeconds,
  formatOvertime,
  formatRemaining,
  isFinished,
  localExtend,
  localPause,
  localResume,
  overtimeOf,
  percentDone,
  remainingSeconds,
  startLabel,
  tabTitle,
} from './timer-math'
import type { FocusTimer } from './types'

const START = Date.parse('2026-10-05T04:30:00Z')
const at = (seconds: number) => START + seconds * 1000
const iso = (seconds: number) => new Date(at(seconds)).toISOString()

const timer = (patch: Partial<FocusTimer> = {}): FocusTimer => ({
  phase: 'focus',
  status: 'running',
  round_number: 1,
  rounds_before_long: 4,
  cycle_id: 'c',
  preset: 'classic',
  planned_seconds: 1500,
  elapsed_seconds: 0,
  remaining_seconds: 1500,
  extension_count: 0,
  overtime_enabled: false,
  overtime_seconds: 0,
  can_extend: true,
  started_at: iso(0),
  paused_at: null,
  paused_total_seconds: 0,
  pause_count: 0,
  ends_at: iso(1500),
  last_seen_at: iso(0),
  away_pending: false,
  auto_start_breaks: true,
  auto_start_focus: false,
  subject_id: null,
  chapter_id: null,
  activity_type: 'other',
  client_id: 'k',
  version: 1,
  ...patch,
})

describe('countdown', () => {
  it('shows 14:57 after a refresh at 10:03 of a 25 minute round', () => {
    expect(remainingSeconds(timer(), at(603))).toBe(897)
    expect(formatRemaining(897)).toBe('14:57')
  })

  it('freezes while paused and never goes negative', () => {
    const paused = timer({ status: 'paused', paused_at: iso(600) })
    expect(remainingSeconds(paused, at(600))).toBe(900)
    expect(remainingSeconds(paused, at(5000))).toBe(900)
    expect(remainingSeconds(timer(), at(99999))).toBe(0)
  })

  it('leaves a finished pause out of the round', () => {
    expect(remainingSeconds(timer({ paused_total_seconds: 300 }), at(900))).toBe(900)
    expect(elapsedSeconds(timer({ paused_total_seconds: 300 }), at(100))).toBe(0)
  })

  it('finishes only when running and at zero', () => {
    expect(isFinished(timer(), at(1499))).toBe(false)
    expect(isFinished(timer(), at(1500))).toBe(true)
    expect(isFinished(timer({ status: 'paused', paused_at: iso(10) }), at(99999))).toBe(false)
  })

  it('counts a 3 minute extension of the clock, not of the wall', () => {
    const extended = localExtend(timer())
    expect(extended.planned_seconds).toBe(1800)
    expect(remainingSeconds(extended, at(1500))).toBe(300)
  })

  it('reports progress as a percentage', () => {
    expect(percentDone(timer(), at(750))).toBe(50)
    expect(percentDone(timer(), at(99999))).toBe(100)
  })
})

describe('format', () => {
  it('uses hours only from an hour on', () => {
    expect(formatRemaining(0)).toBe('00:00')
    expect(formatRemaining(59)).toBe('00:59')
    expect(formatRemaining(3600)).toBe('1:00:00')
    expect(formatRemaining(7384)).toBe('2:03:04')
  })

  it('puts the countdown first in the tab title', () => {
    expect(tabTitle(timer(), at(48), 'Focus timer')).toBe('24:12 Focus')
    expect(tabTitle(timer({ phase: 'short_break', planned_seconds: 300 }), at(0), 'Focus timer')).toBe('05:00 Break')
    expect(tabTitle(timer({ status: 'paused', paused_at: iso(60) }), at(900), 'Focus timer')).toBe('Paused 24:00')
    expect(tabTitle(null, at(0), 'Focus timer')).toBe('Focus timer')
  })

  it('labels Start with the remembered round', () => {
    expect(startLabel(null)).toBe('Start')
    expect(startLabel({ next_phase: 'focus', next_round: 1, rounds_before_long: 4, cycle_id: null })).toBe('Start')
    expect(startLabel({ next_phase: 'focus', next_round: 3, rounds_before_long: 4, cycle_id: 'c' })).toBe(
      'Start round 3 of 4',
    )
    expect(startLabel({ next_phase: 'long_break', next_round: 4, rounds_before_long: 4, cycle_id: 'c' })).toBe(
      'Start long break',
    )
  })
})

describe('offline copies of the actions', () => {
  it('pause then resume matches what the server will compute', () => {
    const paused = localPause(timer(), iso(600))
    expect(paused.status).toBe('paused')
    expect(localPause(paused, iso(700))).toBe(paused)
    const resumed = localResume(paused, iso(900))
    expect(resumed.paused_total_seconds).toBe(300)
    expect(remainingSeconds(resumed, at(900))).toBe(900)
    expect(resumed.ends_at).toBe(iso(1800))
  })

  it('stops extending after three times', () => {
    let t = timer()
    for (let i = 0; i < 5; i++) t = localExtend(t)
    expect(t.extension_count).toBe(3)
    expect(t.planned_seconds).toBe(2400)
    expect(t.can_extend).toBe(false)
  })
})

describe('overtime', () => {
  const over = (patch = {}) => timer({ overtime_enabled: true, ...patch })

  it('counts up from the planned length and not before', () => {
    expect(overtimeOf(over(), at(1499))).toBeNull()
    expect(overtimeOf(over(), at(1500))).toBe(0)
    expect(overtimeOf(over(), at(1500 + 723))).toBe(723)
    expect(formatOvertime(723)).toBe('+12:03')
  })

  it('freezes while paused', () => {
    const paused = over({ status: 'paused', paused_at: iso(1800) })
    expect(overtimeOf(paused, at(9999))).toBe(300)
  })

  it('does not apply to rounds started without it, breaks, or an away round', () => {
    expect(overtimeOf(timer(), at(2000))).toBeNull()
    expect(overtimeOf(over({ phase: 'short_break' }), at(2000))).toBeNull()
    expect(overtimeOf(over({ status: 'away' }), at(2000))).toBeNull()
  })

  it('shows in the tab title', () => {
    expect(tabTitle(over(), at(1500 + 65), 'Focus timer')).toBe('+01:05 Focus')
  })
})
