import { describe, expect, it } from 'vitest'

import {
  capacityPercent,
  gotWorse,
  groupMilestones,
  healthView,
  milestoneTitle,
  movedNote,
  nextReplanText,
  optionView,
  replanSummary,
  statusNote,
} from './planner'
import type { Milestone } from './planner-types'

const milestone = (over: Partial<Milestone> = {}): Milestone => ({
  id: 'm1',
  kind: 'finish_reading',
  subject_key: 'taxation',
  subject_id: null,
  subject_name: 'Taxation',
  target_date: '2026-12-01',
  original_target_date: '2026-12-01',
  moved_days: 0,
  overdue_days: 0,
  remaining_minutes: 120,
  status: 'pending',
  done_at: null,
  ...over,
})

describe('healthView', () => {
  it('names the shortfall for a plan that is behind', () => {
    const view = healthView({ health: 'at_risk', shortfall_minutes: 150, remaining_minutes: 600 })
    expect(view).toMatchObject({ label: 'At risk', tone: 'bad' })
    expect(view.headline).toContain('2 h 30 min')
  })
  it('is calm when on track and quiet when there is nothing to plan', () => {
    expect(healthView({ health: 'on_track', shortfall_minutes: 0, remaining_minutes: 10 }).tone).toBe('good')
    expect(healthView({ health: 'unknown', shortfall_minutes: 0, remaining_minutes: 0 }).tone).toBe('quiet')
  })
})

describe('capacityPercent', () => {
  it('is 0 with nothing left, 100 with no room, and capped at 100', () => {
    expect(capacityPercent({ capacity_minutes: 100, remaining_minutes: 0 })).toBe(0)
    expect(capacityPercent({ capacity_minutes: 0, remaining_minutes: 30 })).toBe(100)
    expect(capacityPercent({ capacity_minutes: 200, remaining_minutes: 50 })).toBe(25)
    expect(capacityPercent({ capacity_minutes: 100, remaining_minutes: 300 })).toBe(100)
  })
})

describe('milestones', () => {
  it('titles each kind with the paper', () => {
    expect(milestoneTitle(milestone())).toBe('Finish reading Taxation')
    expect(milestoneTitle(milestone({ kind: 'mock' }))).toBe('Mock test: Taxation')
    expect(milestoneTitle(milestone({ kind: 'exam_week', subject_name: null, subject_key: '' }))).toContain('Exam week')
    expect(milestoneTitle(milestone({ subject_name: null }))).toBe('Finish reading taxation')
  })
  it('says how far a date moved', () => {
    expect(movedNote(milestone())).toBeNull()
    expect(movedNote(milestone({ moved_days: 6 }))).toBe('Moved 6 days later')
    expect(movedNote(milestone({ moved_days: -1 }))).toBe('Moved 1 day earlier')
  })
  it('notes overdue and at-risk milestones', () => {
    expect(statusNote(milestone({ overdue_days: 3 }))).toBe('Overdue by 3 days')
    expect(statusNote(milestone({ status: 'at_risk' }))).toBe('At risk')
    expect(statusNote(milestone())).toBeNull()
    expect(statusNote(milestone({ status: 'done' }))).toBe('Done')
  })
  it('lists open milestones by date and finished ones apart', () => {
    const groups = groupMilestones([
      milestone({ id: 'b', target_date: '2026-12-10' }),
      milestone({ id: 'a', target_date: '2026-12-01' }),
      milestone({ id: 'c', status: 'done' }),
    ])
    expect(groups.open.map((m) => m.id)).toEqual(['a', 'b'])
    expect(groups.finished.map((m) => m.id)).toEqual(['c'])
  })
})

describe('optionView', () => {
  it('explains more time with the numbers', () => {
    const view = optionView({ option: 'more_time', daily_minutes: 150, extra_minutes: 30, feasible: true })
    expect(view.detail).toContain('2 h 30 min a day')
    expect(view.feasible).toBe(true)
  })
  it('says when an option cannot close the gap', () => {
    expect(
      optionView({ option: 'skim_low_weight', chapter_count: 9, saved_minutes: 90, feasible: false }).feasible,
    ).toBe(false)
    expect(
      optionView({ option: 'next_attempt', exam_date: null, shortfall_minutes: null, feasible: false }).detail,
    ).toContain('no later attempt')
  })
})

describe('re-plan wording', () => {
  it('summarises what moved', () => {
    expect(replanSummary({ trigger: 'manual', moved_count: 0, health_after: 'on_track' })).toBe(
      'Your plan was re-planned when you asked. Nothing needed to move.',
    )
    expect(replanSummary({ trigger: 'weekly', moved_count: 1, health_after: 'on_track' })).toContain('1 date moved')
  })
  it('knows when the plan got worse', () => {
    expect(gotWorse('on_track', 'at_risk')).toBe(true)
    expect(gotWorse('at_risk', 'on_track')).toBe(false)
    expect(gotWorse('at_risk', 'at_risk')).toBe(false)
  })
  it('shows the next automatic check only when there is one', () => {
    expect(nextReplanText({ next_replan_on: null })).toBeNull()
    expect(nextReplanText({ next_replan_on: '2026-10-19' })).toContain('Mon 19 Oct')
  })
})
