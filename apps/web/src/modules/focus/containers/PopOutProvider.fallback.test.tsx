import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  track: vi.fn(),
  flag: true,
  user: { id: 'u1' } as { id: string } | null,
  failed: vi.fn(),
  blocked: vi.fn(),
}))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ user: state.user, loading: false }) }))
vi.mock('../lib/notify', () => ({ notify: { popOutFailed: state.failed, miniWindowBlocked: state.blocked } }))

import { fakePipWindow, removePipStub, stubPip } from '~/test/pip-window'

import { usePopOut } from '../hooks/usePopOut'
import { PopOutButton } from './PopOutButton'
import { PopOutProvider } from './PopOutProvider'

function Probe() {
  const pop = usePopOut()
  return (
    <>
      <p data-testid="mode">{pop.available ? 'pip' : pop.fallback ? 'window' : 'none'}</p>
      <button onClick={() => void pop.open('pill', { source: 'focus_page', timer: 'focus' })}>open</button>
      <PopOutButton source="mini" timer="focus" />
    </>
  )
}

const mount = () =>
  render(
    <PopOutProvider>
      <Probe />
    </PopOutProvider>,
  )
const mode = () => screen.getByTestId('mode').textContent

beforeEach(() => {
  state.flag = true
  state.user = { id: 'u1' }
  vi.clearAllMocks()
})
afterEach(() => {
  removePipStub()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('PopOutProvider: the fallback window (X-01 W4.4)', () => {
  it('offers the small window on a desktop browser without Document Picture-in-Picture', () => {
    mount()
    expect(mode()).toBe('window')
    expect(screen.getByRole('button', { name: 'Pop out the timer' })).toBeInTheDocument()
  })

  it('opens /app/focus/mini from the click, as a named small window, and tracks popout_opened supported window', async () => {
    const focus = vi.fn()
    const open = vi.spyOn(window, 'open').mockReturnValue({ focus } as unknown as Window)
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'Pop out the timer' }))
    expect(open).toHaveBeenCalledWith('/app/focus/mini', 'artha-timer', 'popup,width=320,height=220')
    expect(focus).toHaveBeenCalledOnce()
    expect(state.track).toHaveBeenCalledWith('popout_opened', {
      supported: 'window',
      size: 'pill',
      source: 'mini',
      timer: 'focus',
    })
  })

  it('a second click goes to the same named window, and the button never turns into Bring back', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue({ focus: vi.fn() } as unknown as Window)
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'Pop out the timer' }))
    await userEvent.click(screen.getByRole('button', { name: 'Pop out the timer' }))
    expect(open).toHaveBeenCalledTimes(2)
    expect(open.mock.calls[1]?.[1]).toBe('artha-timer')
    expect(screen.queryByRole('button', { name: 'Bring the timer back' })).toBeNull()
  })

  it('says so when the browser blocks the pop-up, and does not track an open', async () => {
    vi.spyOn(window, 'open').mockReturnValue(null)
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'Pop out the timer' }))
    expect(state.blocked).toHaveBeenCalledOnce()
    expect(state.track).not.toHaveBeenCalledWith('popout_opened', expect.anything())
  })

  it('uses Picture-in-Picture, not the small window, where the browser has it', async () => {
    const open = vi.spyOn(window, 'open')
    stubPip(fakePipWindow())
    mount()
    expect(mode()).toBe('pip')
    await userEvent.click(screen.getByRole('button', { name: 'open' }))
    expect(open).not.toHaveBeenCalled()
  })

  it('offers nothing on a phone, with the flag off, or when signed out', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const phone = mount()
    expect(mode()).toBe('none')
    expect(screen.queryByRole('button', { name: 'Pop out the timer' })).toBeNull()
    phone.unmount()
    vi.unstubAllGlobals()
    state.flag = false
    const off = mount()
    expect(mode()).toBe('none')
    off.unmount()
    state.flag = true
    state.user = null
    mount()
    expect(mode()).toBe('none')
  })
})
