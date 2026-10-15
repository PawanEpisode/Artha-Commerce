import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  query: {} as Record<string, unknown>,
  actions: {} as Record<string, unknown>,
  navigate: vi.fn(),
}))
vi.mock('@tanstack/react-router', async () => {
  const stub = (await import('~/test/router-stub')).routerStub
  return { ...stub, useNavigate: () => state.navigate }
})
vi.mock('../hooks/useTodayFlag', () => ({ useTodayFlag: () => state.flag }))
vi.mock('../hooks/useTodayQueries', () => ({
  useTodayPlan: () => state.query,
  useTodaySettings: () => ({ data: { show_tomorrow: false } }),
  useDayPreview: () => ({ data: undefined }),
}))
vi.mock('../hooks/useTaskActions', () => ({ useTaskActions: () => state.actions }))
vi.mock('~/modules/personalization', () => ({ useBootstrap: () => ({ data: { first_name: 'Aarav' } }) }))
vi.mock('~/modules/tracker', () => ({
  useSubjectOptionsState: () => ({ options: [], loading: false }),
  useChapterOptionsState: () => ({ options: [], loading: false }),
}))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  markCelebrated: vi.fn().mockResolvedValue({}),
}))

import { plan, task } from '../lib/fixtures'
import type { OpenResult } from '../lib/types'
import { TodayContainer } from './TodayContainer'

const ok = (data: OpenResult) => ({ isPending: false, isError: false, error: null, data, refetch: vi.fn() })
const renderIt = (search: object = {}) =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TodayContainer search={search} />
    </QueryClientProvider>,
  )

beforeEach(() => {
  state.flag = true
  state.query = ok(plan([]))
  state.navigate = vi.fn()
  state.actions = {
    tick: vi.fn(),
    skip: vi.fn(),
    snooze: vi.fn(),
    swap: vi.fn(),
    remove: vi.fn(),
    undo: vi.fn(),
    start: vi.fn().mockResolvedValue({ path: '/app/recall', search: { a: 1 } }),
    add: vi.fn(),
    edit: vi.fn(),
    canUndo: () => null,
    busy: new Set(),
  }
})

describe('TodayContainer states', () => {
  it('is unavailable while the flag is off', () => {
    state.flag = false
    renderIt()
    expect(screen.getByText('Today is not available yet')).toBeTruthy()
  })

  it('shows a loading status, then an error with retry', () => {
    state.query = { isPending: true, isError: false, error: null, data: undefined, refetch: vi.fn() }
    const { unmount } = renderIt()
    expect(screen.getByRole('status', { name: "Loading today's plan" })).toBeTruthy()
    unmount()
    state.query = { isPending: false, isError: true, error: new Error('x'), data: undefined, refetch: vi.fn() }
    renderIt()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('handles a student with no enrolment and one past the exam', () => {
    const empty = { version: 0, date: '2026-10-14', tz: 'UTC', server_time: '', plan: null }
    state.query = ok({ ...empty, state: 'not_enrolled' })
    const { unmount } = renderIt()
    expect(screen.getByText('Choose a course to get a daily plan')).toBeTruthy()
    unmount()
    state.query = ok({ ...empty, state: 'post_exam' })
    renderIt()
    expect(screen.getByText('Your exam date has passed')).toBeTruthy()
  })

  it('says nothing is due when the plan is empty', () => {
    renderIt()
    expect(screen.getByText('Nothing is due today')).toBeTruthy()
  })

  it('lists open, done and skipped tasks, the starter, the partial notice and the ring text', () => {
    state.query = ok(
      plan([task('a', 'suggested'), task('b', 'done'), task('c', 'skipped')], { starter_task_id: 'a', partial: true }),
    )
    renderIt()
    expect(screen.getByRole('heading', { name: 'Good morning, Aarav' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Start here: Task a/ })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'To do' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Done' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Skipped and snoozed' })).toBeTruthy()
    expect(screen.getByText(/Some suggestions are missing/)).toBeTruthy()
    expect(screen.getByRole('progressbar', { name: "Today's tasks" }).getAttribute('aria-valuetext')).toBe(
      '1 of 3 tasks done',
    )
    expect(screen.getByText(/about 10 min left/)).toBeTruthy()
  })

  it('ticks from the checkbox and starts from the button, then opens the task with where it came from', async () => {
    state.query = ok(plan([task('a', 'suggested'), task('b', 'suggested')]))
    renderIt()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark done: Task a' }))
    expect((state.actions.tick as ReturnType<typeof vi.fn>).mock.calls[0]?.[0]).toMatchObject({ id: 'a' })
    fireEvent.click(screen.getByRole('button', { name: 'Start: Task b' }))
    await vi.waitFor(() => expect(state.navigate).toHaveBeenCalled())
    expect(state.navigate.mock.calls[0]?.[0]).toMatchObject({
      to: '/app/recall',
      search: { a: 1, from: 'today', task: 'b' },
    })
  })

  it('asks "also log it" before ticking a task with a manual action', () => {
    state.query = ok(
      plan([task('a', 'suggested', { manual_action: { label: 'Also log this revision', default: true } })]),
    )
    renderIt()
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark done: Task a' }))
    expect(state.actions.tick).not.toHaveBeenCalled()
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('Also log this revision')).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Mark done' }))
    expect((state.actions.tick as ReturnType<typeof vi.fn>).mock.calls[0]).toEqual([
      expect.objectContaining({ id: 'a' }),
      true,
    ])
  })

  it('opens the menu with swap, snooze and skip for a suggestion, and edit and delete for an own task', () => {
    state.query = ok(plan([task('a', 'suggested'), task('o', 'suggested', { origin: 'user' })]))
    renderIt()
    fireEvent.click(screen.getByRole('button', { name: 'More actions for Task a' }))
    let dialog = screen.getByRole('dialog')
    for (const name of ['Why this?', 'Swap for another', 'Snooze', 'Skip'])
      expect(within(dialog).getByRole('button', { name })).toBeTruthy()
    expect(within(dialog).queryByRole('button', { name: 'Delete' })).toBeNull()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Swap for another' }))
    expect((state.actions.swap as ReturnType<typeof vi.fn>).mock.calls[0]?.[0]).toMatchObject({ id: 'a' })
    fireEvent.click(screen.getByRole('button', { name: 'More actions for Task o' }))
    dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('button', { name: 'Edit' })).toBeTruthy()
    expect(within(dialog).getByRole('button', { name: 'Delete' })).toBeTruthy()
    expect(within(dialog).queryByRole('button', { name: 'Swap for another' })).toBeNull()
  })

  it('skips with a chosen reason', () => {
    state.query = ok(plan([task('a', 'suggested')]))
    renderIt()
    fireEvent.click(screen.getByRole('button', { name: 'More actions for Task a' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Skip' }))
    fireEvent.click(screen.getByRole('radio', { name: 'No time today' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Skip' }))
    expect(state.actions.skip).toHaveBeenCalledWith(expect.objectContaining({ id: 'a' }), 'no_time')
  })

  it('opens the add sheet from ?add and checks the form before sending', () => {
    state.query = ok(plan([task('a', 'suggested')]))
    renderIt({ add: true })
    const dialog = screen.getByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Add task/ }))
    expect(within(dialog).getByText('Give the task a title.')).toBeTruthy()
    expect(state.actions.add).not.toHaveBeenCalled()
  })

  it('celebrates a finished day, and closes a mostly skipped one calmly', () => {
    state.query = ok(
      plan([task('a', 'done'), task('b', 'done')], { celebrate: true, closing: 'celebrate', streak: 12 }),
    )
    const { unmount } = renderIt()
    expect(screen.getByRole('heading', { name: 'Day complete' })).toBeTruthy()
    expect(screen.getByText('12 day streak')).toBeTruthy()
    unmount()
    state.query = ok(plan([task('a', 'done'), task('b', 'skipped'), task('c', 'skipped')], { closing: 'calm' }))
    renderIt()
    expect(screen.getByText('You did 1 and skipped 2. Tomorrow is a fresh start.')).toBeTruthy()
  })

  it('welcomes a student back with a lighter day, without streak-loss wording', () => {
    state.query = ok(plan([task('a', 'suggested')], { budget_source: 'comeback' }))
    renderIt()
    expect(screen.getByRole('heading', { name: 'Welcome back, Aarav' })).toBeTruthy()
    expect(screen.getByText('A lighter day to ease back in.')).toBeTruthy()
  })

  it('shows the overload notice and the long-day note', () => {
    state.query = ok(
      plan([task('a', 'suggested', { est_minutes: 200 })], {
        backlog: [
          {
            kind: 'revision',
            count: 38,
            scheduled: 3,
            label: '38 revisions are overdue, 3 are scheduled today',
            link: { path: '/app/revision', search: {} },
          },
        ],
      }),
    )
    renderIt()
    expect(screen.getByRole('link', { name: /38 revisions are overdue/ }).getAttribute('href')).toBe('/app/revision')
    expect(screen.getByText(/That is a long day/)).toBeTruthy()
  })
})
