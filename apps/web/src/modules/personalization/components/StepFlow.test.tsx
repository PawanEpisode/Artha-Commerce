import { Celebration, StepFlow } from '@artha/design-system'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import confetti from '~/test/confetti-stub'

const steps = ['Profile', 'Course', 'Hours']

describe('StepFlow', () => {
  it('announces the step and offers Back only when asked', async () => {
    const onBack = vi.fn()
    const { rerender } = render(
      <StepFlow steps={steps} current={1} title="Pick your course">
        <p>body</p>
      </StepFlow>,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Step 2 of 3: Pick your course')
    expect(screen.queryByRole('button', { name: /back/i })).toBeNull()

    rerender(
      <StepFlow steps={steps} current={1} title="Pick your course" onBack={onBack}>
        <p>body</p>
      </StepFlow>,
    )
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalledOnce()
  })

  it('moves focus to the heading when the step changes, not on first render', () => {
    const { rerender } = render(
      <StepFlow steps={steps} current={0} title="One">
        <input aria-label="x" />
      </StepFlow>,
    )
    expect(screen.getByRole('heading', { name: 'One' })).not.toHaveFocus()
    rerender(
      <StepFlow steps={steps} current={1} title="Two">
        <input aria-label="x" />
      </StepFlow>,
    )
    expect(screen.getByRole('heading', { name: 'Two' })).toHaveFocus()
  })

  it('clamps an out-of-range step instead of throwing', () => {
    render(<StepFlow steps={steps} current={9} title="Late" />)
    expect(screen.getByRole('status')).toHaveTextContent('Step 3 of 3')
  })
})

describe('Celebration', () => {
  const matchMedia = (reduce: boolean) =>
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: reduce && q.includes('reduce'), media: q }))

  beforeEach(() => {
    vi.useFakeTimers()
    confetti.mockClear()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the message, fires confetti once and continues by itself exactly once', async () => {
    matchMedia(false)
    const onContinue = vi.fn()
    render(<Celebration title="All set" message="Aarav, CMA Final is set up." ctaLabel="Go" onContinue={onContinue} />)
    expect(screen.getByRole('dialog', { name: 'All set' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Aarav, CMA Final is set up.')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10)
    })
    expect(confetti).toHaveBeenCalledOnce()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2600)
    })
    expect(onContinue).toHaveBeenCalledOnce()
  })

  it('does not call onContinue twice when the button is clicked first', async () => {
    matchMedia(false)
    const onContinue = vi.fn()
    render(<Celebration title="t" message="m" ctaLabel="Go" onContinue={onContinue} />)
    act(() => screen.getByRole('button', { name: 'Go' }).click())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000)
    })
    expect(onContinue).toHaveBeenCalledOnce()
  })

  it('stays still under reduced motion and does not auto-continue when disabled', async () => {
    matchMedia(true)
    const onContinue = vi.fn()
    render(<Celebration title="t" message="m" ctaLabel="Go" onContinue={onContinue} autoContinueMs={0} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(confetti).not.toHaveBeenCalled()
    expect(onContinue).not.toHaveBeenCalled()
  })
})
