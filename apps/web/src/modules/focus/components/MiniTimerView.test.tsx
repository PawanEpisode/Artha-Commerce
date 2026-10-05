import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { MiniTimerView } from './MiniTimerView'

const props = {
  label: 'Focus round',
  phase: 'focus' as const,
  paused: false,
  clock: '24:12',
  spoken: '24 min 12 s left',
  busy: false,
  onPause: vi.fn(),
  onResume: vi.fn(),
  renderLink: (children: React.ReactNode) => <a href="/app/focus">{children}</a>,
}

describe('MiniTimerView', () => {
  it('names the running timer and links to it', () => {
    render(<MiniTimerView {...props} />)
    expect(screen.getByRole('region', { name: 'Running focus round' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /open the focus round\. 24 min 12 s left/i })).toHaveAttribute(
      'href',
      '/app/focus',
    )
  })

  it('pauses and resumes', async () => {
    const onPause = vi.fn()
    const onResume = vi.fn()
    const { rerender } = render(<MiniTimerView {...props} onPause={onPause} onResume={onResume} />)
    await userEvent.click(screen.getByRole('button', { name: 'Pause focus round' }))
    expect(onPause).toHaveBeenCalledOnce()
    rerender(<MiniTimerView {...props} paused onPause={onPause} onResume={onResume} />)
    await userEvent.click(screen.getByRole('button', { name: 'Resume focus round' }))
    expect(onResume).toHaveBeenCalledOnce()
  })

  it('has no pause button during a break', () => {
    render(
      <MiniTimerView {...props} phase="short_break" label="Short break" onPause={undefined} onResume={undefined} />,
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
