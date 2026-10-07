import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  track: vi.fn(),
  flag: true,
  user: { id: 'u1' } as { id: string } | null,
  failed: vi.fn(),
}))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ user: state.user, loading: false }) }))
vi.mock('../lib/notify', () => ({ notify: { popOutFailed: state.failed } }))

import { fakePipWindow, removePipStub, stubPip } from '~/test/pip-window'

import { usePopOut } from '../hooks/usePopOut'
import { PopOutProvider } from './PopOutProvider'

function Probe() {
  const pop = usePopOut()
  return (
    <>
      <p data-testid="status">{pop.available ? (pop.isOpen ? 'open' : 'available') : 'unavailable'}</p>
      <button onClick={() => void pop.open('card', { source: 'focus_page', timer: 'focus' })}>open</button>
      <button onClick={() => void pop.resize('pill')}>shrink</button>
      <button onClick={() => void pop.resize('card')}>grow</button>
      <button onClick={pop.close}>close</button>
    </>
  )
}

const mount = () =>
  render(
    <PopOutProvider>
      <Probe />
    </PopOutProvider>,
  )
const status = () => screen.getByTestId('status').textContent

beforeEach(() => {
  state.flag = true
  state.user = { id: 'u1' }
  state.track.mockClear()
  state.failed.mockClear()
})
afterEach(() => removePipStub())

describe('PopOutProvider', () => {
  it('offers nothing in a browser without Document Picture-in-Picture', () => {
    mount()
    expect(status()).toBe('unavailable')
  })

  it('offers nothing while the floating_timer flag is off, or when signed out', () => {
    stubPip(fakePipWindow())
    state.flag = false
    const { unmount } = mount()
    expect(status()).toBe('unavailable')
    unmount()
    state.flag = true
    state.user = null
    mount()
    expect(status()).toBe('unavailable')
  })

  it('opens the window from a click and tracks popout_opened with where, what and how big', async () => {
    const requestWindow = stubPip(fakePipWindow())
    mount()
    expect(status()).toBe('available')
    await userEvent.click(screen.getByText('open'))
    expect(requestWindow).toHaveBeenCalledWith({ width: 320, height: 300 })
    expect(status()).toBe('open')
    expect(state.track).toHaveBeenCalledWith('popout_opened', {
      supported: 'pip',
      size: 'card',
      source: 'focus_page',
      timer: 'focus',
    })
  })

  it('says so, once, when the browser refuses to open it', async () => {
    stubPip(new DOMException('needs a click', 'NotAllowedError'))
    mount()
    await userEvent.click(screen.getByText('open'))
    expect(status()).toBe('available')
    expect(state.failed).toHaveBeenCalledOnce()
    expect(state.track).not.toHaveBeenCalledWith('popout_opened', expect.anything())
  })

  it('tracks popout_closed with the seconds it was open when the student closes it', async () => {
    const win = fakePipWindow()
    stubPip(win)
    mount()
    await userEvent.click(screen.getByText('open'))
    await userEvent.click(screen.getByText('close'))
    expect(status()).toBe('available')
    expect(state.track).toHaveBeenCalledWith('popout_closed', { seconds_open: expect.any(Number), by: 'student' })
  })

  it('closes an open window when the flag goes off, and says that is why', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const { rerender } = mount()
    await userEvent.click(screen.getByText('open'))
    expect(status()).toBe('open')
    state.flag = false
    await act(async () => {
      rerender(
        <PopOutProvider>
          <Probe />
        </PopOutProvider>,
      )
    })
    expect(win.close).toHaveBeenCalledOnce()
    expect(status()).toBe('unavailable')
    expect(state.track).toHaveBeenCalledWith('popout_closed', expect.objectContaining({ by: 'flag_off' }))
  })

  it('closes an open window when the student signs out', async () => {
    const win = fakePipWindow()
    stubPip(win)
    const { rerender } = mount()
    await userEvent.click(screen.getByText('open'))
    state.user = null
    await act(async () => {
      rerender(
        <PopOutProvider>
          <Probe />
        </PopOutProvider>,
      )
    })
    expect(win.close).toHaveBeenCalledOnce()
  })

  it('tracks popout_size_changed with whether the browser really resized the window', async () => {
    // The stand-in window is 320 x 156 and never resizes by itself, like a browser that refuses.
    stubPip(fakePipWindow())
    mount()
    await userEvent.click(screen.getByText('open'))
    await userEvent.click(screen.getByText('grow'))
    await waitFor(() =>
      expect(state.track).toHaveBeenCalledWith('popout_size_changed', { size: 'card', resized: false }),
    )
    await userEvent.click(screen.getByText('shrink'))
    await waitFor(() =>
      expect(state.track).toHaveBeenCalledWith('popout_size_changed', { size: 'pill', resized: true }),
    )
  })
})
