import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PopOutPromptCard } from './PopOutPromptCard'

const setup = (always = false) => {
  const handlers = { onAlwaysChange: vi.fn(), onPopOut: vi.fn(), onNotNow: vi.fn() }
  render(<PopOutPromptCard always={always} {...handlers} />)
  return handlers
}

describe('PopOutPromptCard', () => {
  it('asks the question with Pop out, Not now and the every-time box, as a labelled region and not a dialog', () => {
    setup()
    expect(screen.getByRole('region', { name: 'Keep the timer on top while you study?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Pop out/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Not now' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Do this every time I start a round' })).not.toBeChecked()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('does not take focus when it appears', () => {
    setup()
    expect(document.body).toHaveFocus()
  })

  it('announces itself once, politely', async () => {
    setup()
    const status = screen.getByRole('status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(await screen.findByText(/keep the timer on top of your other windows/)).toBeInTheDocument()
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('reports each choice', async () => {
    const h = setup()
    await userEvent.click(screen.getByRole('checkbox'))
    expect(h.onAlwaysChange).toHaveBeenCalledWith(true)
    await userEvent.click(screen.getByRole('button', { name: /Pop out/ }))
    expect(h.onPopOut).toHaveBeenCalledOnce()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(h.onNotNow).toHaveBeenCalledOnce()
  })

  it('reaches every control with the keyboard, in reading order', async () => {
    setup()
    await userEvent.tab()
    expect(screen.getByRole('checkbox')).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: /Pop out/ })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Not now' })).toHaveFocus()
  })

  it('keeps the buttons at least 40 px tall (they wrap instead of shrinking)', () => {
    setup()
    for (const name of [/Pop out/, 'Not now']) expect(screen.getByRole('button', { name })).toHaveClass('min-h-11')
  })
})
