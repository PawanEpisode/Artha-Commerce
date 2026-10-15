import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  query: {} as Record<string, unknown>,
}))
vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useTodayFlag', () => ({ useTodayFlag: () => state.flag }))
vi.mock('../hooks/useTodayQueries', () => ({ useTodayPlan: () => state.query }))
vi.mock('~/modules/personalization', () => ({ useBootstrap: () => ({ data: { first_name: 'Aarav' } }) }))

import type { OpenResult, Plan, Task } from '../lib/types'
import { TodayContainer } from './TodayContainer'

const task = (id: string, state: Task['state'], extra: Partial<Task> = {}): Task => ({
  id,
  origin: 'provider',
  kind: 'mcq',
  slot: 'mcq',
  title: `Task ${id}`,
  reason: 'Due for revision',
  reason_code: 'custom',
  why: { modifiers: [], signals: {} },
  est_minutes: 10,
  progress: null,
  target: null,
  state,
  link: { path: '/app/recall', search: {} },
  subject_id: null,
  chapter_id: null,
  manual_action: null,
  is_must_do: false,
  version: 1,
  ...extra,
})

const plan = (tasks: Task[], extra: Partial<Plan> = {}): Plan => ({
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
  planned_minutes: 30,
  counts: {
    planned: tasks.length,
    done: tasks.filter((t) => t.state === 'done').length,
    open: tasks.filter((t) => t.state === 'suggested' || t.state === 'accepted').length,
    skipped: 0,
    snoozed: 0,
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
})

const ok = (data: OpenResult) => ({ isPending: false, isError: false, error: null, data, refetch: vi.fn() })
const search = {}

describe('TodayContainer states', () => {
  beforeEach(() => {
    state.flag = true
    state.query = ok(plan([]))
  })

  it('is unavailable while the flag is off', () => {
    state.flag = false
    render(<TodayContainer search={search} />)
    expect(screen.getByText('Today is not available yet')).toBeTruthy()
  })

  it('shows a loading status, then an error with retry', () => {
    state.query = { isPending: true, isError: false, error: null, data: undefined, refetch: vi.fn() }
    const { unmount } = render(<TodayContainer search={search} />)
    expect(screen.getByRole('status', { name: "Loading today's plan" })).toBeTruthy()
    unmount()
    state.query = { isPending: false, isError: true, error: new Error('x'), data: undefined, refetch: vi.fn() }
    render(<TodayContainer search={search} />)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('handles a student with no enrolment and one past the exam', () => {
    const empty = { version: 0, date: '2026-10-14', tz: 'UTC', server_time: '', plan: null }
    state.query = ok({ ...empty, state: 'not_enrolled' })
    const { unmount } = render(<TodayContainer search={search} />)
    expect(screen.getByText('Choose a course to get a daily plan')).toBeTruthy()
    unmount()
    state.query = ok({ ...empty, state: 'post_exam' })
    render(<TodayContainer search={search} />)
    expect(screen.getByText('Your exam date has passed')).toBeTruthy()
  })

  it('says nothing is due when the plan is empty', () => {
    render(<TodayContainer search={search} />)
    expect(screen.getByText('Nothing is due today')).toBeTruthy()
  })

  it('lists open, done and skipped tasks, the starter and the partial notice', () => {
    state.query = ok(
      plan([task('a', 'suggested'), task('b', 'done'), task('c', 'skipped')], {
        starter_task_id: 'a',
        partial: true,
      }),
    )
    render(<TodayContainer search={search} />)
    expect(screen.getByRole('heading', { name: 'Good morning, Aarav' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Start here: Task a/ }).getAttribute('href')).toBe('/app/recall')
    expect(screen.getByRole('heading', { name: 'To do' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Done' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Skipped and snoozed' })).toBeTruthy()
    expect(screen.getByText(/Some suggestions are missing/)).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: "Today's tasks" }).getAttribute('aria-valuetext')).toBe(
      '1 of 3 tasks done',
    )
  })

  it('congratulates once everything is done', () => {
    state.query = ok(plan([task('a', 'done'), task('b', 'done')], { celebrate: true }))
    render(<TodayContainer search={search} />)
    expect(screen.getByText("You finished today's plan. Anything left below is optional.")).toBeTruthy()
    expect(screen.getAllByRole('status').some((el) => el.textContent === 'Day complete. Well done.')).toBe(true)
  })
})
