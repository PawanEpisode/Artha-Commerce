import { fireEvent, render, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ mutate: vi.fn() }))
vi.mock('../hooks/useFocusSettings', () => ({ useSaveFocusSettings: () => ({ mutate: state.mutate }) }))
vi.mock('../hooks/useContextLabel', () => ({ useContextLabel: () => 'Taxation · GST: ITC' }))
vi.mock('../lib/chime', () => ({ unlockAudio: vi.fn() }))

import { type FocusTimerApi } from '../hooks/useFocusTimer'
import { type PopOutApi, PopOutContext } from '../hooks/usePopOut'
import type { FocusSettings, FocusTimer, IdleInfo } from '../lib/types'
import { PopOutFocus } from './PopOutFocus'
import { PopOutWindow } from './PopOutWindow'

const NOW = Date.parse('2026-10-05T04:40:00Z')
const iso = (secondsAgo: number) => new Date(NOW - secondsAgo * 1000).toISOString()

const timer = (patch: Partial<FocusTimer> = {}, startedSecondsAgo = 600): FocusTimer =>
  ({
    phase: 'focus',
    status: 'running',
    round_number: 2,
    rounds_before_long: 4,
    planned_seconds: 1500,
    extension_count: 0,
    overtime_enabled: true,
    can_extend: true,
    started_at: iso(startedSecondsAgo),
    paused_at: null,
    paused_total_seconds: 0,
    auto_start_breaks: true,
    subject_id: 's1',
    chapter_id: 'c1',
    activity_type: 'other',
    client_id: 'k',
    version: 1,
    ...patch,
  }) as FocusTimer

const settings = { preset: 'classic' } as FocusSettings

function api(patch: Partial<FocusTimerApi> = {}) {
  return {
    timer: null,
    idle: null,
    settings,
    busy: false,
    announcement: '',
    pause: vi.fn(),
    resume: vi.fn(),
    extend: vi.fn(),
    skipBreak: vi.fn(),
    end: vi.fn(),
    start: vi.fn(),
    claim: { mutate: vi.fn() },
    from: vi.fn((_surface: string, run: () => unknown) => run()),
    ...patch,
  } as unknown as FocusTimerApi
}

/** A second document with its own window, like the floating one (a detached document has no window to query). */
const frames: HTMLIFrameElement[] = []
function makeWindow() {
  const frame = document.createElement('iframe')
  document.body.appendChild(frame)
  frames.push(frame)
  const doc = frame.contentDocument as Document
  const root = doc.createElement('div')
  doc.body.appendChild(root)
  return root
}
const context = (root: HTMLElement | null, size: 'pill' | 'card'): PopOutApi => ({
  available: true,
  fallback: false,
  isOpen: !!root,
  window: null,
  root,
  size,
  open: vi.fn(),
  close: vi.fn(),
  resize: vi.fn().mockResolvedValue(true),
})

function show(f: FocusTimerApi, size: 'pill' | 'card' = 'card', root = makeWindow()) {
  const tree = (api: FocusTimerApi): ReactNode => (
    <PopOutContext.Provider value={context(root, size)}>
      <PopOutWindow>
        <PopOutFocus f={api} />
      </PopOutWindow>
    </PopOutContext.Provider>
  )
  const view = render(tree(f))
  return { root, ui: within(root), update: (next: FocusTimerApi) => view.rerender(tree(next)) }
}
const press = (el: HTMLElement) => fireEvent.click(el)

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
  state.mutate.mockClear()
})
afterEach(() => {
  vi.useRealTimers()
  for (const frame of frames.splice(0)) frame.remove()
})

describe('PopOutWindow', () => {
  it('draws into the window, not into the page', () => {
    const { root, ui } = show(api({ timer: timer() }))
    expect(ui.getByRole('region', { name: 'Artha timer' })).toBeInTheDocument()
    expect(root.querySelector('section')).not.toBeNull()
    expect(document.body.querySelector('section[aria-label="Artha timer"]')).toBeNull()
  })

  it('draws nothing while the window is closed', () => {
    const { container } = render(
      <PopOutContext.Provider value={context(null, 'pill')}>
        <PopOutWindow>
          <p>timer</p>
        </PopOutWindow>
      </PopOutContext.Provider>,
    )
    expect(container).toBeEmptyDOMElement()
  })
})

describe('PopOutFocus: clicks in the window reach the timer actions', () => {
  it('pauses and says the action came from the window', () => {
    const f = api({ timer: timer() })
    const { ui } = show(f, 'pill')
    expect(ui.getByRole('timer')).toHaveAccessibleName('15 minutes left')
    press(ui.getByRole('button', { name: 'Pause' }))
    expect(f.pause).toHaveBeenCalledOnce()
    expect(f.from).toHaveBeenCalledWith('popout', expect.any(Function))
  })

  it('shows the paused round with Resume and resumes', () => {
    const f = api({ timer: timer({ status: 'paused', paused_at: iso(300) }) })
    const { ui } = show(f, 'pill')
    press(ui.getByRole('button', { name: 'Resume' }))
    expect(f.resume).toHaveBeenCalledOnce()
  })

  it('shows subject, ring and the full controls in the card, and extends by five minutes', () => {
    const f = api({ timer: timer({ extension_count: 2 }) })
    const { ui } = show(f)
    expect(ui.getByText('Taxation · GST: ITC')).toBeInTheDocument()
    expect(ui.getByRole('progressbar')).toBeInTheDocument()
    press(ui.getByRole('button', { name: '+5 (1 left)' }))
    expect(f.extend).toHaveBeenCalledOnce()
    expect(ui.getByRole('button', { name: 'End' })).toBeInTheDocument()
  })

  it('asks before ending a round of a minute or more, then saves or discards', () => {
    const f = api({ timer: timer() })
    const { ui } = show(f)
    press(ui.getByRole('button', { name: 'End' }))
    expect(f.end).not.toHaveBeenCalled()
    expect(ui.getByText('End this round?')).toBeInTheDocument()
    press(ui.getByRole('button', { name: 'Save and end' }))
    expect(f.end).toHaveBeenLastCalledWith(true)
    press(ui.getByRole('button', { name: 'End' }))
    press(ui.getByRole('button', { name: 'Discard' }))
    expect(f.end).toHaveBeenLastCalledWith(false)
  })

  it('goes back to the controls on Keep going', () => {
    const { ui } = show(api({ timer: timer() }))
    press(ui.getByRole('button', { name: 'End' }))
    press(ui.getByRole('button', { name: 'Keep going' }))
    expect(ui.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })

  it('ends a round under a minute at once: nothing would be saved', () => {
    const f = api({ timer: timer({}, 30) })
    const { ui } = show(f)
    press(ui.getByRole('button', { name: 'End' }))
    expect(f.end).toHaveBeenCalledWith(false)
    expect(ui.queryByText('End this round?')).toBeNull()
  })

  it('past the target offers Start break (stop and save) and no +5 or End', () => {
    const f = api({ timer: timer({}, 1505) })
    const { ui } = show(f)
    expect(ui.getByRole('timer')).toHaveAccessibleName('5 seconds of extra focus')
    expect(ui.queryByRole('button', { name: /\+5/ })).toBeNull()
    expect(ui.queryByRole('button', { name: 'End' })).toBeNull()
    press(ui.getByRole('button', { name: 'Start break' }))
    expect(f.end).toHaveBeenCalledWith(true)
  })

  it('answers the away question', () => {
    const f = api({ timer: timer({ status: 'away' }, 1700) })
    const { ui } = show(f, 'pill')
    press(ui.getByRole('button', { name: 'Yes' }))
    expect(f.claim.mutate).toHaveBeenCalledWith(true)
    press(ui.getByRole('button', { name: 'No' }))
    expect(f.claim.mutate).toHaveBeenLastCalledWith(false)
  })

  it('skips a break', () => {
    const f = api({ timer: timer({ phase: 'short_break', planned_seconds: 300 }) })
    const { ui } = show(f, 'pill')
    press(ui.getByRole('button', { name: 'Skip break' }))
    expect(f.skipBreak).toHaveBeenCalledOnce()
  })

  it('announces the round end through a polite live region in the window', () => {
    const { ui } = show(api({ announcement: 'Focus round done. Time for a short break.' }))
    expect(ui.getByRole('status')).toHaveTextContent('Focus round done. Time for a short break.')
  })
})

describe('PopOutFocus: the next step when nothing runs', () => {
  const waiting: IdleInfo = { next_phase: 'focus', next_round: 3, rounds_before_long: 4, cycle_id: 'c' }

  it('starts the next round with the subject and chapter of the round it showed', () => {
    const f = api({ timer: timer() })
    const { update, ui } = show(f)
    const next = api({ timer: null, idle: waiting, start: f.start })
    update(next)
    expect(ui.getByText('Break over')).toBeInTheDocument()
    press(ui.getByRole('button', { name: 'Start round 3' }))
    expect(f.start).toHaveBeenCalledWith(
      { preset: 'classic', phase: 'focus', subject_id: 's1', chapter_id: 'c1', activity_type: 'other' },
      { has_subject: true, resumed_cycle: true },
    )
  })

  it('offers only Back to Artha when it never saw a round, and brings the tab forward', () => {
    const focus = vi.spyOn(window, 'focus').mockImplementation(() => undefined)
    const f = api({ idle: waiting })
    const { ui } = show(f, 'pill')
    expect(ui.queryByRole('button', { name: /Start round/ })).toBeNull()
    press(ui.getByRole('button', { name: 'Back to Artha' }))
    expect(focus).toHaveBeenCalledOnce()
    focus.mockRestore()
  })

  it('says nothing runs when nothing is due', () => {
    const { ui } = show(api(), 'pill')
    expect(ui.getByText('No timer running')).toBeInTheDocument()
  })
})
