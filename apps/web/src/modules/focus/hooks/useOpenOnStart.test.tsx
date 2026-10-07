import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  track: vi.fn(),
  flag: true,
  user: { id: 'u1' } as { id: string } | null,
}))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ user: state.user, loading: false }) }))
vi.mock('../lib/notify', () => ({ notify: { popOutFailed: vi.fn() } }))

import { fakePipWindow, removePipStub, stubPip } from '~/test/pip-window'

import { PopOutProvider } from '../containers/PopOutProvider'
import type { FocusSettings } from '../lib/types'
import { useOpenOnStart } from './useOpenOnStart'

const start = vi.fn()

/** A Start button written the way every Start handler is: open first, then send the request. */
function StartButton({ settings }: { settings: Pick<FocusSettings, 'popout_on_start' | 'popout_size'> }) {
  const openOnStart = useOpenOnStart(settings)
  return (
    <button
      onClick={() => {
        openOnStart()
        start()
      }}
    >
      Start
    </button>
  )
}

const mount = (popout_on_start: boolean) =>
  render(
    <PopOutProvider>
      <StartButton settings={{ popout_on_start, popout_size: 'pill' }} />
    </PopOutProvider>,
  )

beforeEach(() => {
  state.flag = true
  state.user = { id: 'u1' }
  state.track.mockClear()
  start.mockClear()
})
afterEach(() => removePipStub())

describe('useOpenOnStart', () => {
  it('asks the browser for the window inside the Start click, before the start request', async () => {
    const requestWindow = stubPip(fakePipWindow())
    mount(true)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(requestWindow).toHaveBeenCalledOnce()
    expect(requestWindow).toHaveBeenCalledWith({ width: 320, height: 156 })
    expect(start).toHaveBeenCalledOnce()
    expect(requestWindow.mock.invocationCallOrder[0]).toBeLessThan(start.mock.invocationCallOrder[0] ?? 0)
    expect(state.track).toHaveBeenCalledWith('popout_opened', expect.objectContaining({ source: 'auto_start' }))
  })

  it('opens it once: the next Start with the window already out does nothing', async () => {
    const requestWindow = stubPip(fakePipWindow())
    mount(true)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(requestWindow).toHaveBeenCalledOnce()
    expect(start).toHaveBeenCalledTimes(2)
  })

  it('still starts the round when the setting is off, without opening anything', async () => {
    const requestWindow = stubPip(fakePipWindow())
    mount(false)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(requestWindow).not.toHaveBeenCalled()
    expect(start).toHaveBeenCalledOnce()
  })

  it('with the flag off nothing opens, and the setting is left alone', async () => {
    const requestWindow = stubPip(fakePipWindow())
    state.flag = false
    mount(true)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(requestWindow).not.toHaveBeenCalled()
    expect(start).toHaveBeenCalledOnce()
  })

  it('does nothing in a browser without Document Picture-in-Picture', async () => {
    mount(true)
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(start).toHaveBeenCalledOnce()
    expect(state.track).not.toHaveBeenCalled()
  })
})
