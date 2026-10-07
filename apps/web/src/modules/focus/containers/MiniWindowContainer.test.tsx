import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  floating: true,
  tracker: true,
  focus: undefined as unknown,
  stopwatch: undefined as unknown,
}))
vi.mock('@tanstack/react-router', () => ({ Navigate: ({ to }: { to: string }) => <p>redirected to {to}</p> }))
vi.mock('~/modules/observability', () => ({
  track: vi.fn(),
  useFeatureFlag: (name: string) => (name === 'floating_timer' ? state.floating : state.tracker),
}))
vi.mock('~/modules/tracker', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  useStopwatch: () => state.stopwatch,
}))
vi.mock('../hooks/useFocusTimer', () => ({ useFocusTimer: () => state.focus }))
vi.mock('../hooks/useFocusSettings', () => ({ useSaveFocusSettings: () => ({ mutate: vi.fn() }) }))
vi.mock('../hooks/useContextLabel', () => ({ useContextLabel: () => 'Taxation · GST: ITC' }))
vi.mock('../lib/chime', () => ({ unlockAudio: vi.fn() }))

import { resetPopoutPresence } from '../lib/popout-presence'
import type { FocusSettings, FocusTimer } from '../lib/types'
import { MiniWindowContainer } from './MiniWindowContainer'

const iso = (secondsAgo: number) => new Date(Date.now() - secondsAgo * 1000).toISOString()
const timer = {
  phase: 'focus',
  status: 'running',
  round_number: 2,
  rounds_before_long: 4,
  planned_seconds: 1500,
  extension_count: 0,
  overtime_enabled: true,
  can_extend: true,
  started_at: iso(600),
  paused_at: null,
  paused_total_seconds: 0,
  auto_start_breaks: true,
  subject_id: 's1',
  chapter_id: 'c1',
  activity_type: 'other',
  client_id: 'k',
  version: 1,
} as FocusTimer

function focusApi(patch: Record<string, unknown> = {}) {
  return {
    timer,
    idle: null,
    settings: { preset: 'classic' } as FocusSettings,
    busy: false,
    announcement: '',
    remaining: 900,
    overtime: null,
    featureDisabled: false,
    query: { isPending: false },
    pause: vi.fn(),
    resume: vi.fn(),
    extend: vi.fn(),
    skipBreak: vi.fn(),
    end: vi.fn(),
    start: vi.fn(),
    claim: { mutate: vi.fn() },
    from: vi.fn((_surface: string, run: () => unknown) => run()),
    ...patch,
  }
}

function resizeTo(width: number, height: number) {
  Object.assign(window, { innerWidth: width, innerHeight: height })
  act(() => void window.dispatchEvent(new Event('resize')))
}

beforeEach(() => {
  state.floating = true
  state.tracker = true
  state.focus = focusApi()
  state.stopwatch = { stopwatch: null, featureDisabled: false }
  localStorage.clear()
  resizeTo(320, 220)
})
afterEach(() => resetPopoutPresence())

describe('MiniWindowContainer (X-01 W4.4)', () => {
  it('sends the student to the focus page with the floating_timer flag off', () => {
    state.floating = false
    render(<MiniWindowContainer />)
    expect(screen.getByText('redirected to /app/focus')).toBeInTheDocument()
  })

  it('sends the student to the focus page when the Pomodoro itself is switched off', () => {
    state.focus = focusApi({ featureDisabled: true })
    render(<MiniWindowContainer />)
    expect(screen.getByText('redirected to /app/focus')).toBeInTheDocument()
  })

  it('draws the pill in a small window and the card once it is wider and taller', () => {
    render(<MiniWindowContainer />)
    expect(screen.getByRole('region', { name: 'Artha timer' })).toBeInTheDocument()
    expect(screen.queryByText('Taxation · GST: ITC')).toBeNull()
    resizeTo(320, 300)
    expect(screen.getByText('Taxation · GST: ITC')).toBeInTheDocument()
    resizeTo(280, 300)
    expect(screen.queryByText('Taxation · GST: ITC')).toBeNull()
  })

  it('has no size toggle (the student resizes the window) and no Back to Artha', () => {
    resizeTo(320, 300)
    render(<MiniWindowContainer />)
    expect(screen.queryByRole('button', { name: /Switch to/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Back to Artha/ })).toBeNull()
  })

  it('runs its own timer: Pause acts on the timer and is reported from the mini window', () => {
    const f = focusApi()
    state.focus = f
    render(<MiniWindowContainer />)
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(f.from).toHaveBeenCalledWith('mini_window', expect.any(Function))
    expect(f.pause).toHaveBeenCalledOnce()
  })

  it('shows the stopwatch instead when one is running', () => {
    state.stopwatch = {
      stopwatch: { status: 'paused', subject_id: null, chapter_id: null, idle_pending: false },
      seconds: 65,
      busy: false,
      featureDisabled: false,
      toggle: { mutate: vi.fn() },
    }
    render(<MiniWindowContainer />)
    expect(screen.getByText(/Stopwatch/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument()
  })

  it('does not look for a stopwatch when the time tracker is off', () => {
    state.tracker = false
    state.stopwatch = { stopwatch: { status: 'running' }, seconds: 5, featureDisabled: false }
    render(<MiniWindowContainer />)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })

  it('says once that the window does not stay on top, and remembers that it said so', () => {
    const first = render(<MiniWindowContainer />)
    expect(screen.getByRole('note')).toHaveTextContent('does not stay on top in this browser')
    fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(screen.queryByRole('note')).toBeNull()
    first.unmount()
    render(<MiniWindowContainer />)
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('waits for the first read without drawing a wrong clock', () => {
    state.focus = focusApi({ timer: null, query: { isPending: true } })
    render(<MiniWindowContainer />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading the timer')
  })
})
