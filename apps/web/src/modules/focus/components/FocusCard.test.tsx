import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { presetTimings } from '../lib/presets'
import type { FocusTimer, IdleInfo } from '../lib/types'
import { FocusCard } from './FocusCard'

const handlers = () => ({
  onTimingsChange: vi.fn(),
  onValueChange: vi.fn(),
  onStart: vi.fn(),
  onStartFocusInsteadOfBreak: vi.fn(),
  onPause: vi.fn(),
  onResume: vi.fn(),
  onExtend: vi.fn(),
  onSkipBreak: vi.fn(),
  onEndEarly: vi.fn(),
})

const base = {
  idle: null as IdleInfo | null,
  remainingSeconds: 1500,
  percent: 0,
  busy: false,
  otherLive: null,
  timings: presetTimings('classic'),
  subjects: [{ id: 's1', name: 'Taxation' }],
  chapters: [],
  value: { subject_id: null, chapter_id: null, activity_type: 'reading' as const },
  announcement: '',
}

const running = (patch: Partial<FocusTimer> = {}): FocusTimer =>
  ({
    phase: 'focus',
    status: 'running',
    round_number: 2,
    rounds_before_long: 4,
    extension_count: 1,
    can_extend: true,
    planned_seconds: 1500,
    subject_id: null,
    chapter_id: null,
    activity_type: 'reading',
    ...patch,
  }) as FocusTimer

describe('FocusCard', () => {
  it('offers Start and the presets when nothing runs', async () => {
    const h = handlers()
    render(<FocusCard {...base} {...h} timer={null} />)
    await userEvent.click(screen.getByRole('button', { name: /^start$/i }))
    expect(h.onStart).toHaveBeenCalledOnce()
    expect(screen.getByRole('radio', { name: 'Deep' })).toBeInTheDocument()
    expect(screen.getByRole('timer')).toHaveAccessibleName(/about 25 minutes left/i)
  })

  it('continues a remembered cycle instead of restarting it', () => {
    const idle = { next_phase: 'focus', next_round: 3, rounds_before_long: 4, cycle_id: 'c' } as const
    render(<FocusCard {...base} {...handlers()} timer={null} idle={idle} />)
    expect(screen.getByRole('button', { name: 'Start round 3 of 4' })).toBeInTheDocument()
    expect(screen.getByText('Round 3 of 4 is next')).toBeInTheDocument()
  })

  it('offers the due break, and a way to skip it', async () => {
    const h = handlers()
    const idle = { next_phase: 'short_break', next_round: 1, rounds_before_long: 4, cycle_id: 'c' } as const
    render(<FocusCard {...base} {...h} timer={null} idle={idle} />)
    expect(screen.getByRole('button', { name: 'Start short break' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Skip the break' }))
    expect(h.onStartFocusInsteadOfBreak).toHaveBeenCalledOnce()
  })

  it('shows pause, extend (with how many are left) and end early while a round runs', async () => {
    const h = handlers()
    render(<FocusCard {...base} {...h} timer={running()} />)
    await userEvent.click(screen.getByRole('button', { name: /pause/i }))
    await userEvent.click(screen.getByRole('button', { name: '+5 min (2 left)' }))
    await userEvent.click(screen.getByRole('button', { name: /end early/i }))
    expect(h.onPause).toHaveBeenCalledOnce()
    expect(h.onExtend).toHaveBeenCalledOnce()
    expect(h.onEndEarly).toHaveBeenCalledOnce()
    expect(screen.queryByRole('radio', { name: 'Deep' })).not.toBeInTheDocument()
  })

  it('disables extending after the third time', () => {
    render(<FocusCard {...base} {...handlers()} timer={running({ extension_count: 3, can_extend: false })} />)
    expect(screen.getByRole('button', { name: '+5 min' })).toBeDisabled()
  })

  it('shows Resume when paused', async () => {
    const h = handlers()
    render(<FocusCard {...base} {...h} timer={running({ status: 'paused' })} />)
    await userEvent.click(screen.getByRole('button', { name: /resume/i }))
    expect(h.onResume).toHaveBeenCalledOnce()
    expect(screen.getByText(/paused/i, { selector: 'span' })).toBeInTheDocument()
  })

  it('shows only Skip break during a break', async () => {
    const h = handlers()
    render(
      <FocusCard
        {...base}
        {...h}
        timer={running({ phase: 'short_break', planned_seconds: 300 })}
        remainingSeconds={300}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /skip break/i }))
    expect(h.onSkipBreak).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: /pause/i })).not.toBeInTheDocument()
  })

  it('blocks Start and says why when the stopwatch is running', () => {
    render(<FocusCard {...base} {...handlers()} timer={null} otherLive="stopwatch" />)
    expect(screen.getByRole('button', { name: /^start$/i })).toBeDisabled()
    expect(screen.getByText(/stopwatch is running/i)).toBeInTheDocument()
  })

  it('has no controls to press while the away question waits', () => {
    render(<FocusCard {...base} {...handlers()} timer={running({ status: 'away' })} />)
    expect(screen.queryByRole('button', { name: /pause|resume|end early|skip/i })).not.toBeInTheDocument()
  })
})
