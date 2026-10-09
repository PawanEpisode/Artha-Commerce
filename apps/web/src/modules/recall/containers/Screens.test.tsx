import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { SETTINGS } from '../lib/testing'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { ForgottenContainer } from './ForgottenContainer'
import { SettingsContainer } from './SettingsContainer'
import { StatsContainer } from './StatsContainer'
import { SummaryContainer } from './SummaryContainer'

type Q = { isPending: boolean; isError: boolean; data: unknown; refetch: () => void }
const q = (over: Partial<Q> = {}): Q => ({
  isPending: false,
  isError: false,
  data: undefined,
  refetch: vi.fn(),
  ...over,
})

const h = vi.hoisted(() => ({
  enabled: true,
  settings: null as unknown,
  forgotten: null as unknown,
  stats: null as unknown,
  summary: { data: null as unknown, loading: false, offline: false },
  save: vi.fn(),
  vacation: vi.fn(),
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => true,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useSettings', () => ({
  useSettings: () => h.settings,
  useSaveSettings: () => ({ mutate: h.save, isPending: false, isError: false, isSuccess: false }),
  useSetVacation: () => ({ mutate: h.vacation, isPending: false, isError: false }),
}))
vi.mock('../hooks/useForgotten', () => ({ useForgotten: () => h.forgotten }))
vi.mock('../hooks/useStats', () => ({
  useStatsSummary: () => h.stats,
  useStatsRetention: () => h.stats,
  useStatsForecast: () => h.stats,
  useStatsChapters: () => h.stats,
}))
vi.mock('../hooks/useSessionSummary', () => ({ useSessionSummary: () => h.summary }))
vi.mock('../hooks/useSync', () => ({
  useSync: () => ({ pending: 0, syncing: false, online: true, last: null, syncNow: vi.fn() }),
}))

beforeEach(() => {
  h.enabled = true
  h.save.mockReset()
  h.vacation.mockReset()
})

describe('flag off', () => {
  it('shows the unavailable page instead of any screen', () => {
    h.enabled = false
    h.settings = q({ data: SETTINGS })
    renderWithQuery(<SettingsContainer />)
    expect(screen.queryByRole('heading', { name: 'Revision settings' })).toBeNull()
  })
})

describe('settings', () => {
  it('loads with a skeleton, then shows the form', async () => {
    h.settings = q({ isPending: true })
    const { container, rerender } = renderWithQuery(<SettingsContainer />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading your settings')
    h.settings = q({ data: SETTINGS })
    rerender(<SettingsContainer />)
    expect(screen.getByRole('heading', { name: 'Revision settings' })).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('offers a retry on error', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    h.settings = q({ isError: true, refetch: retry })
    renderWithQuery(<SettingsContainer />)
    await user.click(screen.getByRole('button', { name: /try again|retry/i }))
    expect(retry).toHaveBeenCalled()
  })
})

describe('forgotten', () => {
  it('says nothing is slipping away when empty', async () => {
    h.forgotten = q({ data: [] })
    const { container } = renderWithQuery(<ForgottenContainer />)
    expect(screen.getByText('Nothing is slipping away')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('lists cards with a link to review them', async () => {
    h.forgotten = q({
      data: [
        {
          card_id: 'c1',
          kind: 'basic',
          front_md: 'What is GST?',
          back_md: 'Tax',
          subject_key: null,
          chapter_id: null,
          importance: 3,
          score: 2,
          lapses: 2,
          agains: 4,
          last_again_at: null,
        },
      ],
    })
    const { container } = renderWithQuery(<ForgottenContainer />)
    expect(screen.getByRole('link', { name: 'Review these 1 cards' })).toHaveAttribute(
      'href',
      '/app/recall/review?source=forgotten',
    )
    await expectNoA11yViolations(container)
  })
})

describe('summary', () => {
  it('says so when the session is not on this device', () => {
    h.summary = { data: null, loading: false, offline: false }
    renderWithQuery(<SummaryContainer sessionId="s1" />)
    expect(screen.getByText(/could not find that session/)).toBeInTheDocument()
  })

  it('shows the finished session', async () => {
    h.summary = {
      data: {
        reviewed: 12,
        newCards: 2,
        ratings: { again: 1, hard: 2, good: 8, easy: 1 },
        activeSeconds: 300,
        streakAfter: 3,
      },
      loading: false,
      offline: false,
    }
    const { container } = renderWithQuery(<SummaryContainer sessionId="s1" />)
    expect(screen.getByText(/You reviewed 12 cards/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to revision' })).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })
})

describe('stats', () => {
  it('shows a retryable error', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    h.stats = q({ isError: true, refetch: retry })
    renderWithQuery(<StatsContainer search={{ range: '30d' }} />)
    await user.click(screen.getAllByRole('button', { name: /try again|retry/i })[0]!)
    expect(retry).toHaveBeenCalled()
  })
})
