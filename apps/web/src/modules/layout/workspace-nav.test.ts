import { describe, expect, it } from 'vitest'

import { SETTINGS_LINKS, STUDY_LINKS, visibleLinks } from './workspace-nav'

const off = {
  focus_timer: false,
  time_tracker: false,
  syllabus_coverage: false,
  notifications_ui: false,
  notes: false,
  recall_system: false,
  today_plan: false,
  today_planner: false,
  question_bank: false,
  pyq_bank: false,
  mcq_bank: false,
}

describe('visibleLinks', () => {
  it('keeps every study and settings link when the flags are on', () => {
    expect(visibleLinks(STUDY_LINKS).map((link) => link.to)).toEqual([
      '/app/today',
      '/app/planner',
      '/app/focus',
      '/app/tracker',
      '/app/syllabus',
      '/app/notes',
      '/app/recall',
      '/app/questions',
      '/app/pyq',
      '/app/mcq',
    ])
    expect(visibleLinks(SETTINGS_LINKS).map((link) => link.to)).toEqual([
      '/app/settings/today',
      '/app/settings/focus',
      '/app/settings/tracker',
      '/app/settings/coverage',
      '/app/settings/notes',
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

  it('shows Notes and its settings only when the notes flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.label)).toEqual([])
    expect(visibleLinks(STUDY_LINKS, { ...off, notes: true }).map((link) => link.label)).toEqual(['Notes'])
    expect(visibleLinks(SETTINGS_LINKS, { ...off, notes: true }).map((link) => link.label)).toEqual([
      'Notes settings',
      'Account',
    ])
  })

  it('shows Today only when the today_plan flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.to)).not.toContain('/app/today')
    expect(visibleLinks(STUDY_LINKS, { ...off, today_plan: true }).map((link) => link.to)).toEqual(['/app/today'])
    expect(visibleLinks(SETTINGS_LINKS, off).map((link) => link.to)).not.toContain('/app/settings/today')
    expect(visibleLinks(SETTINGS_LINKS, { ...off, today_plan: true }).map((link) => link.to)).toEqual([
      '/app/settings/today',
      '/app/account',
    ])
  })

  it('shows the study plan only when the today_planner flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.to)).not.toContain('/app/planner')
    expect(visibleLinks(STUDY_LINKS, { ...off, today_planner: true }).map((link) => link.to)).toEqual(['/app/planner'])
  })

  it('shows Revision only when the recall_system flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.label)).toEqual([])
    expect(visibleLinks(STUDY_LINKS, { ...off, recall_system: true }).map((link) => link.to)).toEqual(['/app/recall'])
  })

  it('shows Questions, Past papers, and MCQ Bank only when their flags are on', () => {
    expect(visibleLinks(STUDY_LINKS, { ...off, question_bank: true }).map((link) => link.to)).toEqual([
      '/app/questions',
    ])
    expect(visibleLinks(STUDY_LINKS, { ...off, pyq_bank: true }).map((link) => link.to)).toEqual(['/app/pyq'])
    expect(visibleLinks(STUDY_LINKS, { ...off, mcq_bank: true }).map((link) => link.to)).toEqual(['/app/mcq'])
  })
})
