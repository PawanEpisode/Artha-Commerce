import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { KeepAwakeChip } from './KeepAwakeChip'

describe('KeepAwakeChip (FR-K4)', () => {
  it('says the screen stays on, in a polite live region', () => {
    render(<KeepAwakeChip status="held" />)
    const region = screen.getByRole('status')
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toHaveTextContent('Screen stays on')
  })

  it('says the screen may sleep when the lock is not held', () => {
    render(<KeepAwakeChip status="sleep" />)
    expect(screen.getByRole('status')).toHaveTextContent('Screen may sleep')
  })

  it('differs by words and icon, not by colour alone', () => {
    const { container, rerender } = render(<KeepAwakeChip status="held" />)
    const held = container.querySelector('svg')?.outerHTML
    rerender(<KeepAwakeChip status="sleep" />)
    expect(container.querySelector('svg')?.outerHTML).not.toBe(held)
  })

  it.each(['off', 'checking', 'unsupported'] as const)('is empty for %s but keeps its live region', (status) => {
    render(<KeepAwakeChip status={status} />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('hides the icon from screen readers', () => {
    const { container } = render(<KeepAwakeChip status="held" />)
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })
})
