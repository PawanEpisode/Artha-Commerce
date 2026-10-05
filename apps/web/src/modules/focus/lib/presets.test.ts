import { describe, expect, it } from 'vitest'

import { describeTimings, presetTimings, timingErrors } from './presets'

describe('timings in hours and minutes', () => {
  it('describes a long deep-work rhythm with hours', () => {
    expect(
      describeTimings({ focus_minutes: 90, short_break_minutes: 10, long_break_minutes: 30, rounds_before_long: 2 }),
    ).toBe('1 h 30 m focus, 10 m break, then a 30 m long break after 2 rounds.')
  })
  it('words limit errors with formatDuration and leaves the round count as a number', () => {
    const errors = timingErrors({ ...presetTimings('classic'), focus_minutes: 130, rounds_before_long: 20 })
    expect(errors.focus_minutes).toBe('Focus length must be between 5 minutes and 2 hours.')
    expect(errors.rounds_before_long).toBe('Rounds before a long break must be between 2 and 8.')
  })
  it('accepts every preset', () => {
    for (const key of ['classic', 'deep', 'light'] as const) expect(timingErrors(presetTimings(key))).toEqual({})
  })
})
