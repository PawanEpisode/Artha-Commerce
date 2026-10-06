import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  mode: 'full' as 'full' | 'update',
  steps: [] as Array<{ key: string; state: string; mandatory: boolean; available: boolean }>,
  complete: vi.fn(),
  track: vi.fn(),
  push: vi.fn(),
}))

vi.mock('@tanstack/react-router', () => ({ useRouter: () => ({ history: { push: state.push } }) }))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ signOut: vi.fn() }) }))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../hooks/useBootstrap', () => ({
  useBootstrap: () => ({
    data: { first_name: 'Aarav', course: null, avatar: { kind: 'initials' } },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))
vi.mock('../hooks/useOnboarding', () => ({
  useOnboardingState: () => ({
    data: { mode: state.mode, steps: state.steps, required_version: 3 },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useCompleteOnboarding: () => ({
    mutate: state.complete,
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
  }),
}))
vi.mock('../components/steps/AlertsStep', () => ({ AlertsStep: () => <p>alerts screen</p> }))

import { OnboardingContainer } from './OnboardingContainer'

const done = (key: string, mandatory = true) => ({ key, state: 'done', mandatory, available: true })
const base = [
  done('profile'),
  done('course'),
  done('hours'),
  done('targets'),
  done('catchup', false),
  done('avatar', false),
]
const alerts = (over = {}) => ({ key: 'alerts', state: 'todo', mandatory: false, available: true, ...over })

function setup(search: { step?: string } = { step: 'alerts' }) {
  const onStep = vi.fn()
  render(<OnboardingContainer search={search} onStep={onStep} destination="/app" />)
  return { onStep }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.flag = true
  state.mode = 'full'
  state.steps = [...base, alerts()]
})

describe('OnboardingContainer: the alerts step (FR-N2)', () => {
  it('opens at ?step=alerts with one h1 and the progress label', async () => {
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'Stay on track with alerts' })).toBeInTheDocument()
    expect(screen.getByText('alerts screen')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(state.track).toHaveBeenCalledWith('onboarding_step_viewed', { step: 'alerts', resumed: true })
  })

  it('resumes on the alerts step when it is the first one left to do', async () => {
    const { onStep } = setup({})
    await waitFor(() => expect(onStep).toHaveBeenCalledWith('alerts', { replace: true }))
  })

  it('is left out while the web flag is off: the flow finishes without it', async () => {
    state.flag = false
    setup()
    await waitFor(() => expect(state.complete).toHaveBeenCalled())
    expect(screen.queryByText('alerts screen')).toBeNull()
  })

  it('is left out when the server does not offer it', async () => {
    state.steps = [...base, alerts({ state: 'unavailable', available: false })]
    setup()
    await waitFor(() => expect(state.complete).toHaveBeenCalled())
    expect(screen.queryByText('alerts screen')).toBeNull()
  })

  it('a returning student who followed the setup card sees only that step', async () => {
    state.mode = 'update'
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'Stay on track with alerts' })).toBeInTheDocument()
    expect(state.complete).not.toHaveBeenCalled()
  })

  it('a returning student with nothing to answer finishes quietly, without a celebration', async () => {
    state.mode = 'update'
    setup({})
    await waitFor(() => expect(state.complete).toHaveBeenCalled())
    const options = state.complete.mock.calls[0]?.[1] as { onSuccess: (c: unknown) => void }
    options.onSuccess({ state: { required_version: 3, mode: 'update', steps: [] } })
    expect(state.push).toHaveBeenCalledWith('/app')
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
