import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ConfidencePicker } from './ConfidencePicker'

describe('ConfidencePicker', () => {
  it('disables every option and says why below 50%', () => {
    render(<ConfidencePicker value={null} onChange={vi.fn()} coveragePct={38} unlocked={false} />)
    for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
    expect(screen.getByText(/Available once this chapter is 50% complete/)).toBeInTheDocument()
  })

  it('lets the student pick, and press again to clear, once unlocked', async () => {
    const onChange = vi.fn()
    render(<ConfidencePicker value="amber" onChange={onChange} coveragePct={60} unlocked />)
    expect(screen.queryByText(/Available once/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /confident$/i }))
    expect(onChange).toHaveBeenCalledWith('green')
    await userEvent.click(screen.getByRole('button', { pressed: true }))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('reports the lock once when it appears, and never when unlocked', () => {
    const shown = vi.fn()
    const { rerender } = render(
      <ConfidencePicker value={null} onChange={vi.fn()} coveragePct={20} unlocked={false} onLockedShown={shown} />,
    )
    rerender(
      <ConfidencePicker value={null} onChange={vi.fn()} coveragePct={25} unlocked={false} onLockedShown={shown} />,
    )
    expect(shown).toHaveBeenCalledTimes(1)
    rerender(<ConfidencePicker value={null} onChange={vi.fn()} coveragePct={60} unlocked onLockedShown={shown} />)
    expect(shown).toHaveBeenCalledTimes(1)
  })
})
