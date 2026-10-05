import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RequireOnboarded } from './RequireOnboarded'

const navigate = vi.fn()
const state = vi.hoisted(() => ({
  flag: true,
  pathname: '/app/tracker',
  href: '/app/tracker?x=1',
  boot: {} as Record<string, unknown>,
  completed: false,
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigate,
  useLocation: ({ select }: { select: (l: { pathname: string; href: string }) => unknown }) =>
    select({ pathname: state.pathname, href: state.href }),
}))
vi.mock('~/modules/auth', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  useAuth: () => ({ user: { id: 'u1' }, signOut: vi.fn() }),
}))
vi.mock('~/modules/observability', () => ({ useFeatureFlag: () => state.flag }))
vi.mock('../hooks/useBootstrap', () => ({ useBootstrap: () => state.boot }))
vi.mock('../lib/completedCache', () => ({ rememberCompleted: vi.fn(), wasCompleted: () => state.completed }))

const onboarding = (status: string) => ({ data: { onboarding: { status } }, isPending: false, isError: false })
const ui = () =>
  render(
    <RequireOnboarded>
      <p>workspace</p>
    </RequireOnboarded>,
  )

describe('RequireOnboarded', () => {
  beforeEach(() => {
    navigate.mockClear()
    Object.assign(state, { flag: true, pathname: '/app/tracker', href: '/app/tracker?x=1', completed: false })
    state.boot = onboarding('completed')
  })

  it('lets a finished student in', () => {
    ui()
    expect(screen.getByText('workspace')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('sends an unfinished student to onboarding and keeps the page they asked for', () => {
    state.boot = onboarding('not_started')
    ui()
    expect(screen.queryByText('workspace')).toBeNull()
    expect(navigate).toHaveBeenCalledWith({ to: '/app/onboarding?next=%2Fapp%2Ftracker%3Fx%3D1', replace: true })
  })

  it('does not loop on the onboarding page itself', () => {
    state.pathname = '/app/onboarding'
    state.boot = onboarding('in_progress')
    ui()
    expect(screen.getByText('workspace')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('is invisible when the flag is off', () => {
    state.flag = false
    state.boot = onboarding('not_started')
    ui()
    expect(screen.getByText('workspace')).toBeInTheDocument()
    expect(navigate).not.toHaveBeenCalled()
  })

  it('shows a skeleton, not the workspace, while the answer is pending', () => {
    state.boot = { data: undefined, isPending: true, isError: false }
    ui()
    expect(screen.queryByText('workspace')).toBeNull()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
  })

  it('fails open for a student known to be finished when the API is down', () => {
    state.boot = { data: undefined, isPending: false, isError: true, refetch: vi.fn() }
    state.completed = true
    ui()
    expect(screen.getByText('workspace')).toBeInTheDocument()
  })

  it('fails closed for anyone else, with Retry and Sign out', () => {
    state.boot = { data: undefined, isPending: false, isError: true, refetch: vi.fn() }
    ui()
    expect(screen.queryByText('workspace')).toBeNull()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })
})
