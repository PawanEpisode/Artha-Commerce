import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RevisionWidget } from './RevisionWidget'
import { SetupWidget } from './SetupWidget'
import { TodayWidget } from './TodayWidget'

const s = vi.hoisted(() => ({
  goals: {} as Record<string, unknown>,
  due: {} as Record<string, unknown>,
  overview: {} as Record<string, unknown>,
  onboarding: {} as Record<string, unknown>,
  trackerOff: false,
  live: 'none',
  flags: { time_tracker: true, focus_timer: true } as Record<string, boolean>,
  dismissed: [] as string[],
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, ...rest }: { children: React.ReactNode; to: string; params?: unknown; search?: unknown }) => (
    <a href={to} className={(rest as { className?: string }).className}>
      {children}
    </a>
  ),
}))
vi.mock('~/modules/observability', () => ({ useFeatureFlag: (n: string) => s.flags[n] ?? true }))
vi.mock('~/modules/focus', () => ({ useLiveTimer: () => ({ live: s.live }) }))
vi.mock('~/modules/tracker', () => ({
  useGoals: () => s.goals,
  isTrackerOff: () => s.trackerOff,
  formatDuration: (sec: number) => `${Math.floor(sec / 60)} m`,
}))
vi.mock('~/modules/coverage', () => ({ useDue: () => s.due, useOverview: () => s.overview }))
vi.mock('~/modules/personalization', () => ({
  useOnline: () => true,
  useOnboardingState: () => s.onboarding,
  stepCopy: (k: string) => ({ title: k }),
}))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ user: { id: 'u1' } }) }))
vi.mock('../lib/setupCards', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  readDismissed: () => s.dismissed,
  dismiss: (_u: string, k: string) => [...s.dismissed, k],
}))
vi.mock('../lib/notify', () => ({ notify: { setupCardHidden: vi.fn() } }))

const ready = (data: unknown) => ({ data, isPending: false, isError: false, refetch: vi.fn() })

beforeEach(() => {
  s.trackerOff = false
  s.live = 'none'
  s.flags = { time_tracker: true, focus_timer: true }
  s.dismissed = []
})

describe('TodayWidget', () => {
  const goals = (done: number) =>
    ready({ progress: { daily: { percent: 50, done_seconds: done, target_minutes: 120 }, streak: 3 } })

  it('shows day-one wording with nothing logged, then the normal start button', () => {
    s.goals = goals(0)
    const { unmount } = render(<TodayWidget />)
    expect(screen.getByRole('link', { name: 'Start your first round' })).toBeInTheDocument()
    unmount()
    s.goals = goals(600)
    render(<TodayWidget />)
    expect(screen.getByRole('link', { name: 'Start focus round' })).toBeInTheDocument()
  })

  it('offers Resume while a timer is live', () => {
    s.goals = goals(600)
    s.live = 'pomodoro'
    render(<TodayWidget />)
    expect(screen.getByRole('link', { name: 'Resume timer' })).toBeInTheDocument()
  })

  it('draws its own skeleton and error without touching other widgets', () => {
    s.goals = { data: undefined, isPending: true, isError: false, refetch: vi.fn() }
    const { unmount } = render(<TodayWidget />)
    expect(screen.getByRole('status', { name: 'Loading Today' })).toBeInTheDocument()
    unmount()
    s.goals = { data: undefined, isPending: false, isError: true, refetch: vi.fn(), error: new Error('x') }
    render(<TodayWidget />)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('is absent when the tracker is switched off', () => {
    s.goals = goals(0)
    s.flags.time_tracker = false
    const { container } = render(<TodayWidget />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('RevisionWidget', () => {
  const overview = (started: number) => ready({ level: { chapters_started: started } })
  const row = { id: 'r', name: 'Ch 3', overdue_days: 2, subject: { id: 's', name: 'Paper' } }

  it('lists what is due', () => {
    s.due = { ...ready({ results: [row] }), noEnrollment: false }
    s.overview = { ...overview(4), featureDisabled: false }
    render(<RevisionWidget />)
    expect(screen.getByRole('link', { name: /Open Ch 3/ })).toBeInTheDocument()
  })

  it('says "Nothing due" only to a student who has studied, and hides otherwise', () => {
    s.due = { ...ready({ results: [] }), noEnrollment: false }
    s.overview = { ...overview(4), featureDisabled: false }
    const { unmount } = render(<RevisionWidget />)
    expect(screen.getByText('Nothing due. Nice.')).toBeInTheDocument()
    unmount()
    s.overview = { ...overview(0), featureDisabled: false }
    const { container } = render(<RevisionWidget />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('SetupWidget', () => {
  const steps = [{ key: 'avatar', state: 'skipped', mandatory: false, available: true }]

  it('shows a card per skipped step and hides one when asked', async () => {
    s.onboarding = ready({ steps })
    const { rerender } = render(<SetupWidget />)
    expect(screen.getByRole('heading', { name: 'Finish your setup' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Hide Add a photo/ }))
    rerender(<SetupWidget />)
    expect(screen.queryByRole('heading', { name: 'Finish your setup' })).toBeNull()
  })

  it('is absent when nothing was skipped', () => {
    s.onboarding = ready({ steps: [{ ...steps[0], state: 'done' }] })
    const { container } = render(<SetupWidget />)
    expect(container).toBeEmptyDOMElement()
  })
})
