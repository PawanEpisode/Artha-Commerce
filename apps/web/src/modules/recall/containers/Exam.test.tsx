import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { examBlock, quickPlanBody, todayPlan } from '../lib/testing'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { HubContainer } from './HubContainer'
import { QuickContainer } from './QuickContainer'

const h = vi.hoisted(() => ({
  online: true,
  plan: { isPending: false, isError: false, data: undefined as unknown, refetch: vi.fn() },
  quick: { isPending: false, isError: false, data: undefined as unknown, error: null as unknown, refetch: vi.fn() },
  track: vi.fn(),
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => true,
  useOnlineStatus: () => h.online,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useTodayPlan', () => ({ useTodayPlan: () => h.plan }))
vi.mock('../hooks/useQuickPlan', () => ({ useQuickPlan: () => h.quick }))
vi.mock('../hooks/usePack', () => ({
  usePack: () => ({ pack: null, loading: false, stale: false, storedAt: null, error: false, refresh: vi.fn() }),
}))
vi.mock('../hooks/useSync', () => ({
  useSync: () => ({ pending: 0, syncing: false, online: true, last: null, syncNow: vi.fn() }),
}))
vi.mock('../hooks/useSettings', () => ({
  useRebalance: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false }),
  useSetVacation: () => ({ mutate: vi.fn(), isPending: false }),
}))
vi.mock('../lib/analytics', () => ({ trackRecall: h.track }))

const hub = (exam: ReturnType<typeof examBlock> | null) => {
  h.plan = { isPending: false, isError: false, data: todayPlan({ exam }), refetch: vi.fn() }
  return renderWithQuery(<HubContainer />)
}
const quick = (state: Partial<typeof h.quick>, search = {}) => {
  h.quick = { isPending: false, isError: false, data: undefined, error: null, refetch: vi.fn(), ...state }
  return renderWithQuery(<QuickContainer search={search} />)
}
const apiError = (status: number, code: string) => new ApiError(status, code, { error: { code, message: 'x' } })

beforeEach(() => {
  h.online = true
  h.track.mockReset()
})

describe('the exam strip on the hub', () => {
  it('is absent without an exam date', () => {
    hub(null)
    expect(screen.queryByText(/to your exam/)).not.toBeInTheDocument()
  })

  it('shows the countdown and no extra calls to action far from the exam', async () => {
    const { container } = hub(examBlock())
    expect(screen.getByRole('heading', { name: '36 days to your exam' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Plan quick revision' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /cram/i })).not.toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('invites to quick revision when the plan has enough cards and stays quiet when it does not', () => {
    const q = { candidates: 90, selected: 80, cut_off: 10, per_day: 3, minutes_per_day: 1, too_few: false }
    const { unmount } = hub(examBlock({ quick: q }))
    expect(screen.getByRole('link', { name: 'Plan quick revision' })).toHaveAttribute('href', '/app/recall/quick')
    unmount()
    hub(examBlock({ quick: { ...q, too_few: true } }))
    expect(screen.queryByRole('link', { name: 'Plan quick revision' })).not.toBeInTheDocument()
  })

  it('opens the cram in the last day and says it does not change the schedule', async () => {
    const { container } = hub(examBlock({ days_to_exam: 0.4, cram_open: true }))
    expect(screen.getByRole('heading', { name: 'Your exam is within a day' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Last-day cram' })).toHaveAttribute(
      'href',
      '/app/recall/review?source=cram',
    )
    expect(screen.getByText(/does not change your schedule/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('tells the pacing arithmetic and reports the view without any text', () => {
    hub(
      examBlock({
        pacing: {
          unseen: 100,
          window_days: 46,
          new_per_day: 2,
          introduced_at_limit: 92,
          needed_per_day: 3,
          feasible: false,
        },
      }),
    )
    expect(screen.getByTestId('pacing')).toHaveTextContent('Raise new cards to 3 a day')
    expect(h.track).toHaveBeenCalledWith('recall_pacing_viewed', {
      feasible: false,
      needed_per_day: 3,
      days_to_exam: 36,
    })
  })
})

describe('the quick revision screen', () => {
  it('shows the plan, the minute choices and where start goes', async () => {
    const { container } = quick({ data: quickPlanBody() }, { minutes: 20 })
    expect(screen.getByRole('heading', { name: '380 cards to refresh' })).toBeInTheDocument()
    expect(screen.getByText(/20 cards did not fit/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start quick revision' })).toHaveAttribute(
      'href',
      '/app/recall/review?source=quick',
    )
    expect(screen.getByRole('link', { name: '30 min' })).toHaveAttribute('href', '/app/recall/quick?minutes=30')
    expect(screen.getByRole('link', { name: '20 min' })).toHaveAttribute('aria-current', 'true')
    expect(h.track).toHaveBeenCalledWith('recall_quick_planned', {
      days_to_exam: 36,
      set_size: 380,
      cut_off: 20,
      minutes_per_day: 20,
    })
    await expectNoA11yViolations(container)
  })

  it('says the memory looks solid when too few cards would fade, with no start button', () => {
    quick({ data: quickPlanBody({ too_few: true, candidates: 7, selected: 7, cut_off: 0 }) })
    expect(screen.getByRole('heading', { name: 'Your memory looks solid' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Start quick revision' })).not.toBeInTheDocument()
  })

  it('asks for an exam date, and treats a passed date as information', async () => {
    const { container, unmount } = quick({ isError: true, error: apiError(422, 'no_exam_date') })
    expect(screen.getByRole('link', { name: 'Set exam date' })).toHaveAttribute('href', '/app/settings/coverage')
    await expectNoA11yViolations(container)
    unmount()
    quick({ isError: true, error: apiError(422, 'exam_passed') })
    expect(screen.getByText(/exam date has passed/)).toBeInTheDocument()
  })

  it('has loading, failure and offline states', async () => {
    const { unmount } = quick({ isPending: true })
    expect(screen.getByRole('status')).toHaveTextContent('Planning')
    unmount()
    const err = quick({ isError: true, error: apiError(500, 'server_error') })
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    err.unmount()
    h.online = true
    h.online = false
    const off = quick({ isPending: true })
    expect(screen.getByText('You are offline')).toBeInTheDocument()
    await expectNoA11yViolations(off.container)
  })
})
