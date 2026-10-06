import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ putStep: vi.fn(), skipStep: vi.fn(), track: vi.fn() }))

vi.mock('~/modules/observability', () => ({ track: state.track }))
vi.mock('../../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  putStep: state.putStep,
  skipStep: state.skipStep,
}))
// The notifications module owns the screen; here it is a stand-in with the two buttons the flow cares about.
vi.mock('~/modules/notifications', () => ({
  AlertsStepContainer: ({
    onFinish,
    onSkip,
  }: {
    onFinish: (r: 'granted') => Promise<void>
    onSkip: () => Promise<void>
  }) => (
    <div>
      <button onClick={() => void onFinish('granted').catch(() => undefined)}>finish</button>
      <button onClick={() => void onSkip()}>skip</button>
    </div>
  ),
}))

import { AlertsStep } from './AlertsStep'

const bootstrap = {} as never
function setup() {
  const onDone = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
      <AlertsStep bootstrap={bootstrap} onDone={onDone} />
    </QueryClientProvider>,
  )
  return onDone
}

const stateBody = { steps: [], status: 'in_progress' }

beforeEach(() => {
  vi.clearAllMocks()
  state.putStep.mockResolvedValue(stateBody)
  state.skipStep.mockResolvedValue(stateBody)
})

describe('AlertsStep', () => {
  it('saves the onboarding step through the owning API and moves on', async () => {
    const onDone = setup()
    await userEvent.click(screen.getByRole('button', { name: 'finish' }))
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
    expect(state.putStep).toHaveBeenCalledWith('alerts', {})
    expect(state.track).toHaveBeenCalledWith('onboarding_step_completed', { step: 'alerts' })
  })

  it('does not move on when the API refuses the step (no decision recorded)', async () => {
    state.putStep.mockRejectedValue(new Error('400'))
    const onDone = setup()
    await userEvent.click(screen.getByRole('button', { name: 'finish' }))
    await waitFor(() => expect(state.putStep).toHaveBeenCalled())
    expect(onDone).not.toHaveBeenCalled()
  })

  it('skips through the skip endpoint when alerts are not available in this build', async () => {
    const onDone = setup()
    await userEvent.click(screen.getByRole('button', { name: 'skip' }))
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
    expect(state.skipStep).toHaveBeenCalledWith('alerts')
  })
})
