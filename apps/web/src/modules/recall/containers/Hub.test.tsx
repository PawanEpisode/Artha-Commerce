import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiCard, apiPack, todayPlan } from '../lib/testing'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { HubContainer } from './HubContainer'

const h = vi.hoisted(() => ({
  enabled: true,
  online: true,
  plan: { isPending: false, isError: false, data: undefined as unknown, refetch: vi.fn() },
  pack: { pack: null as unknown, loading: false, stale: false, storedAt: null, error: false, refresh: vi.fn() },
  sync: { pending: 0, syncing: false, online: true, last: null, syncNow: vi.fn() },
  rebalance: vi.fn(),
  vacation: vi.fn(),
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => h.online,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useTodayPlan', () => ({ useTodayPlan: () => h.plan }))
vi.mock('../hooks/usePack', () => ({ usePack: () => h.pack }))
vi.mock('../hooks/useSync', () => ({ useSync: () => h.sync }))
vi.mock('../hooks/useSettings', () => ({
  useRebalance: () => ({ mutate: h.rebalance, isPending: false, isSuccess: false }),
  useSetVacation: () => ({ mutate: h.vacation, isPending: false }),
}))

const show = (plan: unknown) => {
  h.plan = { isPending: false, isError: false, data: plan, refetch: vi.fn() }
  const out = renderWithQuery(<HubContainer />)
  return out
}

beforeEach(() => {
  h.enabled = true
  h.online = true
  h.sync = { pending: 0, syncing: false, online: true, last: null, syncNow: vi.fn() }
  h.pack = { pack: null, loading: false, stale: false, storedAt: null, error: false, refresh: vi.fn() }
  h.rebalance.mockReset()
  h.vacation.mockReset()
})

describe('the revision hub', () => {
  it('shows today and a way to start', async () => {
    const { container } = show(todayPlan())
    expect(screen.getByRole('heading', { name: '20 cards for today' })).toBeInTheDocument()
    expect(screen.getByText('About 12 min')).toBeInTheDocument()
    expect(screen.getByText('4 days in a row')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start reviewing' })).toHaveAttribute(
      'href',
      '/app/recall/review?source=today',
    )
    await expectNoA11yViolations(container)
  })

  it('says a huge backlog in days of work, with no giant number, and offers to spread it', async () => {
    const user = userEvent.setup()
    const { container } = show(
      todayPlan({
        catchup: { active: true, due: 900, oldest_overdue_days: 12 },
        days_to_clear: 9,
        queue_size: 100,
        mode: 'catchup',
      }),
    )
    expect(screen.getByRole('heading', { name: "Let's get you back on track" })).toBeInTheDocument()
    expect(screen.getByText(/clears in about 9 days/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /900/ })).toBeNull()
    expect(screen.getByRole('link', { name: 'Start catch-up' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Spread it over the next 7 days' }))
    expect(h.rebalance).toHaveBeenCalledWith(7)
    await expectNoA11yViolations(container)
  })

  it('celebrates being caught up and offers to review ahead', async () => {
    const { container } = show(todayPlan({ queue_size: 0, counts: { new: 0, learning: 0, due: 0 } }))
    expect(screen.getByRole('heading', { name: 'All caught up' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review ahead 10 cards' })).toHaveAttribute(
      'href',
      expect.stringContaining('ahead=true'),
    )
    await expectNoA11yViolations(container)
  })

  it('guides a student with no cards to their notes', async () => {
    const { container } = show(
      todayPlan({
        counts: { new: 0, learning: 0, due: 0 },
        tiles: [],
        next_due_at: null,
        new_available: 0,
        queue_size: 0,
        streak: 0,
      }),
    )
    expect(screen.getByRole('heading', { name: 'No revision cards yet' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to my notes' })).toHaveAttribute('href', '/app/notes')
    await expectNoA11yViolations(container)
  })

  it('pauses on vacation and lets the student end it', async () => {
    const user = userEvent.setup()
    const { container } = show(todayPlan({ vacation_until: '2026-10-20' }))
    expect(screen.getByRole('heading', { name: 'You are on vacation' })).toBeInTheDocument()
    expect(screen.getByText(/Your streak is safe/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'End vacation now' }))
    expect(h.vacation).toHaveBeenCalledWith(null)
    await expectNoA11yViolations(container)
  })

  it('lists cards that are slipping away with a way to review them', () => {
    show(
      todayPlan({
        forgotten: [
          {
            card_id: 'c1',
            kind: 'definition',
            front_md: 'What is **nexus**?',
            back_md: 'x',
            subject_key: 'law',
            chapter_id: null,
            importance: 1,
            score: 4,
            lapses: 1,
            agains: 3,
            last_again_at: null,
          },
        ],
      }),
    )
    expect(screen.getByRole('heading', { name: 'Slipping away' })).toBeInTheDocument()
    expect(screen.getByText('nexus')).toBeInTheDocument()
    expect(screen.getByText(/Missed 3 times recently/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review these' })).toHaveAttribute(
      'href',
      '/app/recall/review?source=forgotten',
    )
  })

  it('works offline from the cards on the device', async () => {
    h.online = false
    h.sync = { ...h.sync, online: false }
    h.pack = { ...h.pack, pack: apiPack([apiCard(1), apiCard(2), apiCard(3)]) }
    h.plan = { isPending: false, isError: true, data: undefined, refetch: vi.fn() }
    const { container } = renderWithQuery(<HubContainer />)
    expect(screen.getByRole('heading', { name: '3 cards on this device' })).toBeInTheDocument()
    expect(screen.getByText(/Offline/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start reviewing' })).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('asks the student to connect once when there is nothing stored and no connection', () => {
    h.online = false
    h.plan = { isPending: false, isError: true, data: undefined, refetch: vi.fn() }
    renderWithQuery(<HubContainer />)
    expect(screen.getByRole('heading', { name: 'You are offline' })).toBeInTheDocument()
  })

  it('shows a loading state, then an error with a retry', async () => {
    const user = userEvent.setup()
    h.plan = { isPending: true, isError: false, data: undefined, refetch: vi.fn() }
    const first = renderWithQuery(<HubContainer />)
    expect(screen.getByRole('status')).toHaveTextContent("Loading today's revision")
    first.unmount()
    const refetch = vi.fn()
    h.plan = { isPending: false, isError: true, data: undefined, refetch }
    const { container } = renderWithQuery(<HubContainer />)
    expect(screen.getByRole('alert')).toHaveTextContent("We could not load today's revision")
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(refetch).toHaveBeenCalled()
    await expectNoA11yViolations(container)
  })

  it('shows nothing of the feature when the flag is off', () => {
    h.enabled = false
    show(todayPlan())
    expect(screen.getByRole('heading', { name: 'Revision cards are not available yet' })).toBeInTheDocument()
    expect(screen.queryByText('Start reviewing')).toBeNull()
  })

  it('says how many reviews wait to sync', () => {
    h.sync = { pending: 7, syncing: false, online: true, last: null, syncNow: vi.fn() }
    show(todayPlan())
    expect(screen.getByText(/7 waiting/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sync now' })).toBeInTheDocument()
  })
})
