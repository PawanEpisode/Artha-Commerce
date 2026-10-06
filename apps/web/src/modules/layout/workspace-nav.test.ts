import { describe, expect, it } from 'vitest'

import { SETTINGS_LINKS, STUDY_LINKS, visibleLinks } from './workspace-nav'

const off = { focus_timer: false, time_tracker: false, syllabus_coverage: false, notifications_ui: false }

describe('visibleLinks', () => {
  it('keeps every study and settings link when the flags are on', () => {
    expect(visibleLinks(STUDY_LINKS).map((link) => link.to)).toEqual(['/app/focus', '/app/tracker', '/app/syllabus'])
    expect(visibleLinks(SETTINGS_LINKS).map((link) => link.to)).toEqual([
      '/app/settings/focus',
      '/app/settings/tracker',
      '/app/settings/coverage',
      '/app/settings/notifications',
      '/app/account',
    ])
  })

  it('hides a tool and its settings when that flag is off, and always keeps Account', () => {
    const enabled = { ...off, time_tracker: true }
    expect(visibleLinks(STUDY_LINKS, enabled).map((link) => link.label)).toEqual(['Time tracker'])
    expect(visibleLinks(SETTINGS_LINKS, enabled).map((link) => link.label)).toEqual(['Tracker settings', 'Account'])
  })

  it('hides the notification settings when notifications_ui is off, and shows them when it is on', () => {
    const labels = (flags: typeof off) => visibleLinks(SETTINGS_LINKS, flags).map((link) => link.label)
    expect(labels(off)).toEqual(['Account'])
    expect(labels({ ...off, notifications_ui: true })).toEqual(['Notification settings', 'Account'])
  })
})
