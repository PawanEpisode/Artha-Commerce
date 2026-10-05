import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AwayDialog } from './AwayDialog'
import { EndEarlyDialog } from './EndEarlyDialog'

describe('EndEarlyDialog', () => {
  it('saves the studied minutes with the chosen reason', async () => {
    const onEnd = vi.fn()
    render(<EndEarlyDialog open studiedSeconds={754} busy={false} onClose={vi.fn()} onEnd={onEnd} />)
    expect(screen.getByText(/you studied 12 minutes/i)).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('What got in the way?'))
    await userEvent.click(screen.getByRole('option', { name: 'Too tired' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save 12 min' }))
    expect(onEnd).toHaveBeenCalledWith(true, 'tired')
  })

  it('can discard', async () => {
    const onEnd = vi.fn()
    render(<EndEarlyDialog open studiedSeconds={754} busy={false} onClose={vi.fn()} onEnd={onEnd} />)
    await userEvent.click(screen.getByRole('button', { name: 'Discard' }))
    expect(onEnd).toHaveBeenCalledWith(false)
  })

  it('never offers to save under a minute', () => {
    render(<EndEarlyDialog open studiedSeconds={59} busy={false} onClose={vi.fn()} onEnd={vi.fn()} />)
    expect(screen.getByText(/less than a minute is not saved/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^save/i })).not.toBeInTheDocument()
  })
})

describe('AwayDialog', () => {
  it('asks whether the round counts and reports the answer', async () => {
    const onAnswer = vi.fn()
    render(<AwayDialog open plannedSeconds={1500} busy={false} onAnswer={onAnswer} />)
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Did you study through that round?')
    await userEvent.click(screen.getByRole('button', { name: 'Yes, count it' }))
    await userEvent.click(screen.getByRole('button', { name: 'No, discard it' }))
    expect(onAnswer.mock.calls).toEqual([[true], [false]])
  })

  it('cannot be dismissed with Escape', async () => {
    const onAnswer = vi.fn()
    render(<AwayDialog open plannedSeconds={1500} busy={false} onAnswer={onAnswer} />)
    await userEvent.keyboard('{Escape}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onAnswer).not.toHaveBeenCalled()
  })
})
