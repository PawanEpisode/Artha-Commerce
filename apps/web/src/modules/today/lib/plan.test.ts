import { describe, expect, it } from 'vitest'

import { groupTasks, OTHER_KEY, progressText, screenState, selectedTile, starterTask, tileViews } from './plan'
import type { EmptyPlan, Plan, Task } from './types'

const task = (id: string, state: Task['state'], extra: Partial<Task> = {}): Task => ({
  id,
  origin: 'provider',
  kind: 'mcq',
  slot: 'mcq',
  title: `Task ${id}`,
  reason: '',
  reason_code: 'custom',
  why: { modifiers: [], signals: {} },
  est_minutes: 10,
  progress: null,
  target: null,
  state,
  link: null,
  subject_id: null,
  chapter_id: null,
  manual_action: null,
  is_must_do: false,
  version: 1,
  ...extra,
})

const plan = (tasks: Task[], extra: Partial<Plan> = {}): Plan => {
  const planned = tasks.filter((t) => ['suggested', 'accepted', 'done', 'skipped'].includes(t.state))
  return {
    version: 1,
    date: '2026-10-14',
    tz: 'Asia/Kolkata',
    server_time: '2026-10-14T03:00:00Z',
    state: 'ready',
    phase: 'steady',
    days_to_exam: 100,
    generation_no: 1,
    partial: false,
    failed_providers: [],
    budget_minutes: 60,
    planned_minutes: 40,
    counts: {
      planned: planned.length,
      done: planned.filter((t) => t.state === 'done').length,
      open: planned.filter((t) => t.state === 'suggested' || t.state === 'accepted').length,
      skipped: planned.filter((t) => t.state === 'skipped').length,
      snoozed: tasks.filter((t) => t.state === 'snoozed').length,
    },
    starter_task_id: null,
    backlog: [],
    tiles: [],
    tasks,
    streak: null,
    goal: null,
    celebrate: false,
    tomorrow: null,
    ...extra,
  }
}

describe('screenState', () => {
  it('maps the empty answers and the counters', () => {
    const empty = (state: EmptyPlan['state']): EmptyPlan => ({
      version: 0,
      date: '2026-10-14',
      tz: 'UTC',
      server_time: '',
      state,
      plan: null,
    })
    expect(screenState(empty('not_enrolled'))).toBe('not_enrolled')
    expect(screenState(empty('post_exam'))).toBe('post_exam')
    expect(screenState(plan([]))).toBe('nothing_due')
    expect(screenState(plan([task('a', 'suggested')]))).toBe('not_started')
    expect(screenState(plan([task('a', 'done'), task('b', 'suggested')]))).toBe('in_progress')
    expect(screenState(plan([task('a', 'done'), task('b', 'skipped')]))).toBe('all_done')
  })
})

describe('tileViews', () => {
  it('follows the server order and collects unclaimed tasks under Other', () => {
    const tasks = [task('a', 'done'), task('b', 'suggested'), task('c', 'snoozed'), task('d', 'suggested')]
    const p = plan(tasks, {
      tiles: [{ subject_id: 's1', subject_key: 'fr', name: 'Financial Reporting', tasks: ['a', 'b', 'c'] }],
    })
    const views = tileViews(p)
    expect(views.map((v) => v.key)).toEqual(['fr', OTHER_KEY])
    expect(views[0]).toMatchObject({ done: 1, total: 2 }) // the snoozed task is not part of the day
    expect(views[1]?.tasks.map((t) => t.id)).toEqual(['d'])
    expect(selectedTile(views, 'fr')?.name).toBe('Financial Reporting')
    expect(selectedTile(views, 'gone')).toBeNull()
    expect(selectedTile(views, undefined)).toBeNull()
  })
})

describe('groupTasks, starterTask, progressText', () => {
  it('groups by what the student can still do', () => {
    const g = groupTasks([
      task('a', 'accepted'),
      task('b', 'done'),
      task('c', 'skipped'),
      task('d', 'snoozed'),
      task('e', 'expired'),
    ])
    expect([g.open.length, g.done.length, g.parked.length]).toEqual([1, 1, 2])
  })
  it('offers the starter only while it is open', () => {
    expect(starterTask(plan([task('a', 'suggested')], { starter_task_id: 'a' }))?.id).toBe('a')
    expect(starterTask(plan([task('a', 'done')], { starter_task_id: 'a' }))).toBeNull()
    expect(starterTask(plan([task('a', 'suggested')]))).toBeNull()
  })
  it('caps progress at the target', () => {
    expect(progressText(task('a', 'suggested', { progress: { done: 12, target: 30 } }))).toBe('12 of 30')
    expect(progressText(task('a', 'suggested', { progress: { done: 40, target: 30 } }))).toBe('30 of 30')
    expect(progressText(task('a', 'suggested'))).toBeNull()
  })
})
