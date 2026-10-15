import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { task } from '../lib/fixtures'
import { TaskRow } from './TaskRow'

describe('TaskRow stuck prompt (FR-F13-29)', () => {
  it('asks Keep, Snooze or Delete for a stuck own task', () => {
    const onKeep = vi.fn()
    const onStuckSnooze = vi.fn()
    const onStuckDelete = vi.fn()
    const t = { ...task('a', 'suggested'), stuck: true }
    render(<TaskRow task={t} onKeep={onKeep} onStuckSnooze={onStuckSnooze} onStuckDelete={onStuckDelete} />)
    expect(screen.getByText('Still relevant?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Keep' }))
    fireEvent.click(screen.getByRole('button', { name: 'Snooze' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onKeep).toHaveBeenCalledWith(t)
    expect(onStuckSnooze).toHaveBeenCalledWith(t)
    expect(onStuckDelete).toHaveBeenCalledWith(t)
  })

  it('shows no prompt for an ordinary task', () => {
    render(<TaskRow task={task('a', 'suggested')} />)
    expect(screen.queryByText('Still relevant?')).toBeNull()
  })
})
