import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { localStart } from '../lib/stopwatchLocal'
import { StopwatchCard } from './StopwatchCard'

const handlers = () => ({
  onStart: vi.fn(),
  onPause: vi.fn(),
  onResume: vi.fn(),
  onStop: vi.fn(),
  onDiscard: vi.fn(),
  onStillStudying: vi.fn(),
  onValueChange: vi.fn(),
})

const props = {
  seconds: 0,
  busy: false,
  otherLive: null,
  subjects: [{ id: 's1', name: 'Accounting' }],
  chapters: [],
  value: { subject_id: null, chapter_id: null, activity_type: 'reading' as const },
  idlePending: false,
}

const tagged = {
  ...props,
  chapters: [{ id: 'c1', name: 'Chapter 1' }],
  value: { subject_id: 's1', chapter_id: 'c1', activity_type: 'reading' as const },
}

describe('StopwatchCard', () => {
  it('offers Start when a subject and chapter are chosen', async () => {
    const h = handlers()
    render(<StopwatchCard {...tagged} {...h} stopwatch={null} />)
    await userEvent.click(screen.getByRole('button', { name: /start/i }))
    expect(h.onStart).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: /pause/i })).toBeNull()
  })

  it('keeps Start disabled until a subject and a chapter are chosen', () => {
    const { rerender } = render(<StopwatchCard {...props} {...handlers()} stopwatch={null} />)
    expect(screen.getByRole('button', { name: /start/i })).toBeDisabled()
    expect(screen.getByText(/choose a subject and a chapter/i)).toBeInTheDocument()

    rerender(
      <StopwatchCard
        {...tagged}
        {...handlers()}
        stopwatch={null}
        value={{ subject_id: 's1', chapter_id: null, activity_type: 'reading' }}
      />,
    )
    expect(screen.getByRole('button', { name: /start/i })).toBeDisabled()
  })

  it('offers Pause, Stop and Discard while running, and announces the time in words', async () => {
    const h = handlers()
    const sw = localStart('2026-10-05T04:00:00Z', 'c', props.value)
    render(<StopwatchCard {...props} {...h} stopwatch={sw} seconds={3725} />)
    expect(screen.getByRole('timer')).toHaveAccessibleName('Elapsed 1 hour 2 minutes')
    await userEvent.click(screen.getByRole('button', { name: /pause/i }))
    await userEvent.click(screen.getByRole('button', { name: /stop and save/i }))
    await userEvent.click(screen.getByRole('button', { name: /discard/i }))
    expect(h.onPause).toHaveBeenCalledOnce()
    expect(h.onStop).toHaveBeenCalledOnce()
    expect(h.onDiscard).toHaveBeenCalledOnce()
  })

  it('shows Resume when paused', () => {
    const sw = { ...localStart('2026-10-05T04:00:00Z', 'c', props.value), status: 'paused' as const }
    render(<StopwatchCard {...props} {...handlers()} stopwatch={sw} />)
    expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument()
  })

  it('blocks Start while another live timer runs, and says why', () => {
    render(<StopwatchCard {...props} {...handlers()} stopwatch={null} otherLive="pomodoro" />)
    expect(screen.getByRole('button', { name: /start/i })).toBeDisabled()
    expect(screen.getByText(/focus timer is running/i)).toBeInTheDocument()
  })

  it('does not block Start when the server says no other timer is running', () => {
    render(<StopwatchCard {...tagged} {...handlers()} stopwatch={null} otherLive="none" />)
    expect(screen.getByRole('button', { name: /start/i })).toBeEnabled()
    expect(screen.queryByText(/timer is running/i)).toBeNull()
  })

  it('asks "still studying" when the server prompts', async () => {
    const h = handlers()
    const sw = localStart('2026-10-05T04:00:00Z', 'c', props.value)
    render(<StopwatchCard {...props} {...h} stopwatch={sw} idlePending />)
    await userEvent.click(screen.getByRole('button', { name: /still studying/i }))
    expect(h.onStillStudying).toHaveBeenCalledOnce()
  })
})
