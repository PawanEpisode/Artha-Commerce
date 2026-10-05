import { describe, expect, it } from 'vitest'

import { activeSection, TRACKER_SECTIONS } from './sections'

describe('activeSection', () => {
  it('picks the longest matching section', () => {
    expect(activeSection('/app/tracker', TRACKER_SECTIONS)).toBe('today')
    expect(activeSection('/app/tracker/reports', TRACKER_SECTIONS)).toBe('reports')
    expect(activeSection('/app/tracker/goals/', TRACKER_SECTIONS)).toBe('goals')
  })
  it('keeps Today lit for a day page and Settings for tracker settings', () => {
    expect(activeSection('/app/tracker/day/2026-10-05', TRACKER_SECTIONS)).toBe('today')
    expect(activeSection('/app/settings/tracker', TRACKER_SECTIONS)).toBe('settings')
  })
  it('does not match a path that only shares a prefix of letters', () => {
    expect(activeSection('/app/trackers', TRACKER_SECTIONS)).toBeUndefined()
  })
})
