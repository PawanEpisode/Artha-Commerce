import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { type PopoutControl, type PopoutView, popoutView, visibleControls } from '../lib/popout'
import type { FocusTimer, IdleInfo } from '../lib/types'
import { MiniTimerView } from './MiniTimerView'

const START = Date.parse('2026-10-05T04:30:00Z')
const iso = (seconds: number) => new Date(START + seconds * 1000).toISOString()
const timer = (patch: Partial<FocusTimer> = {}): FocusTimer =>
  ({
    phase: 'focus',
    status: 'running',
    round_number: 2,
    rounds_before_long: 4,
    planned_seconds: 1500,
    extension_count: 0,
    overtime_enabled: true,
    can_extend: true,
    started_at: iso(0),
    paused_at: null,
    paused_total_seconds: 0,
    auto_start_breaks: true,
    subject_id: 's1',
    chapter_id: 'c1',
    activity_type: 'other',
    client_id: 'k',
    ...patch,
  }) as FocusTimer
const last = { subject_id: 's1', chapter_id: 'c1', activity_type: 'other' as const }
const waiting: IdleInfo = { next_phase: 'short_break', next_round: 2, rounds_before_long: 4, cycle_id: 'c' }
const at = (seconds: number) => START + seconds * 1000
const views: Array<[string, PopoutView]> = [
  ['focus', popoutView(timer(), null, null, at(228), last)],
  ['paused', popoutView(timer({ status: 'paused', paused_at: iso(100) }), null, null, at(300), last)],
  ['overtime', popoutView(timer(), null, null, at(1505), last)],
  ['away', popoutView(timer({ status: 'away' }), null, null, at(1700), last)],
  ['break', popoutView(timer({ phase: 'short_break', planned_seconds: 300 }), null, null, at(60), last)],
  ['waiting', popoutView(null, waiting, null, at(0), last)],
  ['idle', popoutView(null, null, null, at(0), last)],
  ['stopwatch', popoutView(null, null, { paused: false, seconds: 90 }, at(0), null)],
]
const view = Object.fromEntries(views) as Record<string, PopoutView>

function props(v: PopoutView, size: 'corner' | 'pill' | 'card', overrides = {}) {
  return {
    variant: size,
    view: v,
    controls: size === 'corner' ? v.controls : visibleControls(v.controls, size, true),
    busy: false,
    onControl: vi.fn(),
    ...overrides,
  }
}

describe('MiniTimerView: corner', () => {
  const link = (children: React.ReactNode) => <a href="/app/focus">{children}</a>

  it('names the running timer and links to it', () => {
    render(<MiniTimerView {...props(view.focus!, 'corner', { renderLink: link })} />)
    expect(screen.getByRole('region', { name: 'Running focus round' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the focus round\. 21 minutes 12 seconds left/i })).toHaveAttribute(
      'href',
      '/app/focus',
    )
  })

  it('pauses and resumes', async () => {
    const onControl = vi.fn()
    const { rerender } = render(<MiniTimerView {...props(view.focus!, 'corner', { onControl })} />)
    await userEvent.click(screen.getByRole('button', { name: 'Pause focus round' }))
    expect(onControl).toHaveBeenCalledWith('pause')
    rerender(<MiniTimerView {...props(view.paused!, 'corner', { onControl })} />)
    await userEvent.click(screen.getByRole('button', { name: 'Resume focus round' }))
    expect(onControl).toHaveBeenLastCalledWith('resume')
  })

  it('has no buttons during a break', () => {
    render(<MiniTimerView {...props(view.break!, 'corner')} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('keeps Pause past the target, where the main control is saving the round', async () => {
    render(<MiniTimerView {...props(view.overtime!, 'corner')} />)
    expect(screen.getByRole('button', { name: 'Pause focus round' })).toBeInTheDocument()
  })

  it('shows the extra action after the controls', () => {
    render(<MiniTimerView {...props(view.focus!, 'corner', { action: <button>Pop out the timer</button> })} />)
    expect(screen.getByRole('button', { name: 'Pop out the timer' })).toBeInTheDocument()
  })
})

describe('MiniTimerView: pill', () => {
  it('is the Artha timer, with the exact time as its spoken clock and the clock as text', () => {
    render(<MiniTimerView {...props(view.focus!, 'pill')} />)
    expect(screen.getByRole('region', { name: 'Artha timer' })).toBeInTheDocument()
    expect(screen.getByRole('timer')).toHaveAccessibleName('21 minutes 12 seconds left')
    expect(screen.getByText('21:12')).toBeInTheDocument()
    expect(screen.getByText('Focus round · Round 2 of 4')).toBeInTheDocument()
  })

  it('shows the clock and the first control only', async () => {
    const onControl = vi.fn()
    render(<MiniTimerView {...props(view.focus!, 'pill', { onControl })} />)
    expect(screen.queryByRole('button', { name: /\+5/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Pause' }))
    expect(onControl).toHaveBeenCalledWith('pause')
  })

  it('draws a finished round in the phase-end colour with the one next-step button', () => {
    render(<MiniTimerView {...props(view.waiting!, 'pill')} />)
    expect(screen.getByRole('region', { name: 'Artha timer' })).toHaveClass('bg-success-bg', 'text-success-fg')
    expect(screen.getAllByRole('button', { name: /start break/i })).toHaveLength(1)
    expect(screen.getByText('Round done')).toBeInTheDocument()
  })

  it('announces through a polite live region', () => {
    render(<MiniTimerView {...props(view.focus!, 'pill', { announcement: 'Focus round done.' })} />)
    expect(screen.getByRole('status')).toHaveTextContent('Focus round done.')
  })

  it('switches size with a named button', async () => {
    const onToggleSize = vi.fn()
    render(<MiniTimerView {...props(view.focus!, 'pill', { onToggleSize })} />)
    await userEvent.click(screen.getByRole('button', { name: 'Switch to the card size' }))
    expect(onToggleSize).toHaveBeenCalledOnce()
  })
})

describe('MiniTimerView: card', () => {
  it('shows subject, ring and every control', () => {
    render(<MiniTimerView {...props(view.focus!, 'card', { context: 'Taxation · GST: ITC' })} />)
    expect(screen.getByText('Taxation · GST: ITC')).toBeInTheDocument()
    const ring = screen.getByRole('progressbar')
    expect(within(ring).getByRole('timer')).toHaveAccessibleName('21 minutes 12 seconds left')
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Pause', '+5 (3 left)', 'End'])
  })

  it('disables +5 when it is not allowed', () => {
    const v = popoutView(timer({ extension_count: 3, can_extend: false }), null, null, at(10), last)
    render(<MiniTimerView {...props(v, 'card')} />)
    expect(screen.getByRole('button', { name: '+5' })).toBeDisabled()
  })

  it('asks the away question in words and with Yes and No', () => {
    render(<MiniTimerView {...props(view.away!, 'card')} />)
    expect(screen.getByText('The round ended while you were away. Did you study through it?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Yes' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No' })).toBeInTheDocument()
  })

  it('shows the elapsed stopwatch time without a ring', () => {
    render(<MiniTimerView {...props(view.stopwatch!, 'card')} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(screen.getByRole('timer')).toHaveAccessibleName('Elapsed 1 minute')
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument()
  })

  it('shows the question above the End confirm', () => {
    const confirm: PopoutControl[] = [
      {
        id: 'save_end',
        label: 'Save and end',
        icon: 'check',
        primary: true,
        disabled: false,
        pill: true,
        iconOnly: false,
      },
    ]
    render(<MiniTimerView {...props(view.focus!, 'card', { controls: confirm, prompt: 'End this round?' })} />)
    expect(screen.getByText('End this round?')).toBeInTheDocument()
  })
})

describe('MiniTimerView: touch targets', () => {
  // The design system's button sizes: icon 40, default 44, large 48. Small (36) is never used here.
  const bigEnough = /\b(size-10|min-h-11|min-h-12)\b/

  it.each((['corner', 'pill', 'card'] as const).flatMap((size) => views.map(([name, v]) => [size, name, v] as const)))(
    'every button in the %s for %s is at least 40 px',
    (size, _name, v) => {
      render(<MiniTimerView {...props(v, size, { onToggleSize: vi.fn(), action: undefined })} />)
      for (const button of screen.queryAllByRole('button')) expect(button.className).toMatch(bigEnough)
    },
  )

  it('keeps the confirm buttons big too', () => {
    render(
      <MiniTimerView
        {...props(view.focus!, 'card', {
          controls: [
            {
              id: 'save_end',
              label: 'Save and end',
              icon: 'check',
              primary: true,
              disabled: false,
              pill: true,
              iconOnly: false,
            },
            {
              id: 'keep_going',
              label: 'Keep going',
              icon: 'close',
              primary: false,
              disabled: false,
              pill: true,
              iconOnly: true,
            },
          ],
        })}
      />,
    )
    for (const button of screen.getAllByRole('button')) expect(button.className).toMatch(bigEnough)
  })
})
