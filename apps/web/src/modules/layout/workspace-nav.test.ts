import { describe, expect, it } from 'vitest'

import { SETTINGS_LINKS, STAFF_LINKS, STUDY_LINKS, visibleLinks } from './workspace-nav'

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
  performance_analytics: false,
  paper_analysis: false,
  progression_engine: false,
  amendments: false,
  mock_tests: false,
  study_material: false,
}

describe('visibleLinks', () => {
  it('keeps every study and settings link when the flags are on', () => {
    expect(visibleLinks(STUDY_LINKS).map((link) => link.to)).toEqual([
      '/app/today',
      '/app/planner',
      '/app/focus',
      '/app/tracker',
      '/app/syllabus',
      '/app/analysis',
      '/app/revision',
      '/app/amendments',
      '/app/notifications',
      '/app/notes',
      '/app/recall',
      '/app/vault',
      '/app/material',
      '/app/practice',
      '/app/mocks',
      '/app/questions',
      '/app/pyq',
      '/app/mcq',
      '/app/analytics',
    ])
    expect(visibleLinks(SETTINGS_LINKS).map((link) => link.to)).toEqual([
      '/app/settings/today',
      '/app/settings/focus',
      '/app/settings/tracker',
      '/app/settings/coverage',
      '/app/settings/notes',
      '/app/settings/recall',
      '/app/settings/notifications',
      '/app/settings/analysis',
      '/app/settings/progression',
      '/app/settings/articleship',
      '/app/settings/material',
      '/app/settings/mocks',
      '/app/account',
    ])
  })

  it('lists the pages inside a section and keeps staff tabs out of the study links', () => {
    const recall = STUDY_LINKS.find((link) => link.to === '/app/recall')
    expect(recall?.children?.map((c) => c.to)).toContain('/app/recall/stats')
    expect(STUDY_LINKS.map((link) => link.to)).not.toContain('/app/questions/editor')
    expect(STAFF_LINKS.map((link) => link.to)).toEqual(['/app/questions/editor', '/design-system'])
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
      '/app/practice',
      '/app/questions',
    ])
    expect(visibleLinks(STUDY_LINKS, { ...off, pyq_bank: true }).map((link) => link.to)).toEqual(['/app/pyq'])
    expect(visibleLinks(STUDY_LINKS, { ...off, mcq_bank: true }).map((link) => link.to)).toEqual(['/app/mcq'])
    expect(visibleLinks(STUDY_LINKS, { ...off, performance_analytics: true }).map((link) => link.to)).toEqual([
      '/app/analytics',
    ])
  })

  it('shows Paper Analysis and its settings only when the paper_analysis flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.to)).not.toContain('/app/analysis')
    expect(visibleLinks(STUDY_LINKS, { ...off, paper_analysis: true }).map((link) => link.to)).toEqual([
      '/app/analysis',
    ])
    expect(visibleLinks(SETTINGS_LINKS, off).map((link) => link.to)).not.toContain('/app/settings/analysis')
    expect(visibleLinks(SETTINGS_LINKS, { ...off, paper_analysis: true }).map((link) => link.to)).toEqual([
      '/app/settings/analysis',
      '/app/account',
    ])
    const analysis = STUDY_LINKS.find((link) => link.to === '/app/analysis')
    expect(analysis?.children?.map((c) => c.to)).toEqual(['/app/analysis/plan', '/app/analysis/plan/active'])
  })

  it('shows Past Level Vault and progression settings only when the progression_engine flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.to)).not.toContain('/app/vault')
    expect(visibleLinks(STUDY_LINKS, { ...off, progression_engine: true }).map((link) => link.to)).toEqual([
      '/app/vault',
    ])
    expect(visibleLinks(SETTINGS_LINKS, off).map((link) => link.to)).not.toContain('/app/settings/progression')
    expect(visibleLinks(SETTINGS_LINKS, { ...off, progression_engine: true }).map((link) => link.to)).toEqual([
      '/app/settings/progression',
      '/app/settings/articleship',
      '/app/account',
    ])
  })

  it('shows Amendments only when the amendments flag is on', () => {
    expect(visibleLinks(STUDY_LINKS, off).map((link) => link.to)).not.toContain('/app/amendments')
    expect(visibleLinks(STUDY_LINKS, { ...off, amendments: true }).map((link) => link.to)).toEqual(['/app/amendments'])
    const amendments = STUDY_LINKS.find((link) => link.to === '/app/amendments')
    expect(amendments?.children?.map((c) => c.to)).toEqual(['/app/amendments/archive'])
  })
})
