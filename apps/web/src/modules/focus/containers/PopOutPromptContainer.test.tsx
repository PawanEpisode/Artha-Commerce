import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  track: vi.fn(),
  mutate: vi.fn(),
  flag: true,
  user: { id: 'u1' } as { id: string } | null,
}))
vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('~/modules/auth', () => ({ useAuth: () => ({ user: state.user, loading: false }) }))
vi.mock('../hooks/useFocusSettings', () => ({ useSaveFocusSettings: () => ({ mutate: state.mutate }) }))
vi.mock('../lib/notify', () => ({ notify: { popOutFailed: vi.fn() } }))

import { fakePipWindow, removePipStub, stubPip } from '~/test/pip-window'

import type { FocusSettings, Phase } from '../lib/types'
import { PopOutPromptContainer } from './PopOutPromptContainer'
import { PopOutProvider } from './PopOutProvider'

const settings = (patch: Partial<FocusSettings> = {}) =>
  ({ popout_on_start: false, popout_size: 'card', popout_prompt_seen: false, ...patch }) as FocusSettings

/** `null` stands for settings that have not loaded yet (a default parameter would swallow `undefined`). */
const mount = (phase: Phase | null = 'focus', loaded: FocusSettings | null = settings()) => {
  const s = loaded ?? undefined
  const ui = (p: Phase | null, next: FocusSettings | undefined) => (
    <PopOutProvider>
      <PopOutPromptContainer phase={p} settings={next} />
    </PopOutProvider>
  )
  const view = render(ui(phase, s))
  return { ...view, again: (p: Phase | null, next: FocusSettings | undefined = s) => view.rerender(ui(p, next)) }
}
const card = () => screen.queryByRole('region', { name: 'Keep the timer on top while you study?' })
const seenWrites = () => state.mutate.mock.calls.filter(([patch]) => 'popout_prompt_seen' in patch)

beforeEach(() => {
  state.flag = true
  state.user = { id: 'u1' }
  state.track.mockClear()
  state.mutate.mockClear()
})
afterEach(() => {
  removePipStub()
  vi.unstubAllGlobals()
})

describe('PopOutPromptContainer', () => {
  it('shows the card in a focus round on a desktop browser with the API, and records it as seen once', async () => {
    stubPip(fakePipWindow())
    const view = mount()
    expect(await screen.findByRole('region', { name: 'Keep the timer on top while you study?' })).toBeInTheDocument()
    expect(seenWrites()).toEqual([[{ popout_prompt_seen: true }]])
    expect(state.track).toHaveBeenCalledWith('popout_prompt_shown', {})
    // The saved flag arrives and the card must not vanish under the student's hands, nor write a second time.
    view.again('focus', settings({ popout_prompt_seen: true }))
    view.again('focus', settings({ popout_prompt_seen: true }))
    expect(card()).toBeInTheDocument()
    expect(seenWrites()).toHaveLength(1)
    expect(state.track.mock.calls.filter(([name]) => name === 'popout_prompt_shown')).toHaveLength(1)
  })

  it('never shows (and never writes) in Safari, where there is no Document Picture-in-Picture', () => {
    mount()
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalled()
    expect(state.track).not.toHaveBeenCalled()
  })

  it('never shows on a phone or a tablet', () => {
    stubPip(fakePipWindow())
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    mount()
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalled()
  })

  it('shows nothing with the floating_timer flag off, and keeps the settings as they are', () => {
    stubPip(fakePipWindow())
    state.flag = false
    mount()
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalled()
  })

  it.each([
    ['it was already seen', settings({ popout_prompt_seen: true })],
    ['pop out on start is already on', settings({ popout_on_start: true })],
    ['the settings have not loaded yet', null],
  ])('shows nothing when %s', (_why, s) => {
    stubPip(fakePipWindow())
    mount('focus', s)
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalled()
  })

  it('waits for a focus round: not while idle, not in a break, and a break does not use it up', async () => {
    stubPip(fakePipWindow())
    const view = mount(null)
    expect(card()).toBeNull()
    view.again('short_break')
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalled()
    view.again('focus')
    expect(await screen.findByRole('region')).toBeInTheDocument()
  })

  it('goes away when the round ends and does not come back with the next round', async () => {
    stubPip(fakePipWindow())
    const view = mount()
    expect(await screen.findByRole('region')).toBeInTheDocument()
    view.again('short_break')
    await waitFor(() => expect(card()).toBeNull())
    view.again('focus')
    expect(card()).toBeNull()
    expect(seenWrites()).toHaveLength(1)
  })

  it('Not now just dismisses it: it was already recorded as seen', async () => {
    stubPip(fakePipWindow())
    mount()
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))
    expect(card()).toBeNull()
    expect(state.track).toHaveBeenCalledWith('popout_prompt_answered', { answer: 'not_now', always: false })
    expect(state.mutate).toHaveBeenCalledTimes(1)
    expect(state.mutate).toHaveBeenCalledWith({ popout_prompt_seen: true })
  })

  it('Pop out opens the window at the remembered size without changing the setting', async () => {
    const requestWindow = stubPip(fakePipWindow())
    mount()
    await userEvent.click(await screen.findByRole('button', { name: /Pop out/ }))
    expect(requestWindow).toHaveBeenCalledWith({ width: 320, height: 300 })
    expect(state.track).toHaveBeenCalledWith('popout_prompt_answered', { answer: 'popped_out', always: false })
    await waitFor(() =>
      expect(state.track).toHaveBeenCalledWith('popout_opened', {
        supported: 'pip',
        size: 'card',
        source: 'prompt',
        timer: 'focus',
      }),
    )
    expect(card()).toBeNull()
    expect(state.mutate).not.toHaveBeenCalledWith(expect.objectContaining({ popout_on_start: true }))
  })

  it('Pop out with the box ticked also turns on pop out on start', async () => {
    stubPip(fakePipWindow())
    mount()
    await userEvent.click(await screen.findByRole('checkbox', { name: 'Do this every time I start a round' }))
    await userEvent.click(screen.getByRole('button', { name: /Pop out/ }))
    await waitFor(() => expect(state.mutate).toHaveBeenCalledWith({ popout_on_start: true }))
    expect(state.track).toHaveBeenCalledWith('popout_prompt_answered', { answer: 'popped_out', always: true })
  })

  it('does not turn the setting on when the browser refuses to open the window', async () => {
    stubPip(new DOMException('needs a click', 'NotAllowedError'))
    mount()
    await userEvent.click(await screen.findByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: /Pop out/ }))
    await waitFor(() => expect(card()).toBeNull())
    expect(state.mutate).not.toHaveBeenCalledWith({ popout_on_start: true })
  })

  it('Not now with the box ticked does not turn the setting on', async () => {
    stubPip(fakePipWindow())
    mount()
    await userEvent.click(await screen.findByRole('checkbox'))
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(state.mutate).not.toHaveBeenCalledWith({ popout_on_start: true })
  })
})
