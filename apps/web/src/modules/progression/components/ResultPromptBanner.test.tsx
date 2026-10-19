import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  status: {
    result_prompt: {
      should_prompt: true,
      term_name: 'June 2026',
      level_name: 'Intermediate',
    },
  },
}))

vi.mock('@tanstack/react-router', async () => {
  const stub = (await import('~/test/router-stub')).routerStub
  return stub
})

vi.mock('../hooks/useProgression', () => ({
  useProgressionStatus: () => ({ data: state.status, isLoading: false }),
}))

import { ResultPromptBanner } from './ResultPromptBanner'

describe('ResultPromptBanner', () => {
  it('renders prompt banner when results are announced and should_prompt is true', () => {
    render(<ResultPromptBanner />)
    expect(screen.getByText(/June 2026 Results Announced/)).toBeInTheDocument()
    expect(screen.getByText(/Update My Progress/)).toBeInTheDocument()
  })

  it('dismisses banner when close button is clicked', () => {
    render(<ResultPromptBanner />)
    const closeBtn = screen.getByLabelText('Dismiss banner')
    fireEvent.click(closeBtn)
    expect(screen.queryByText(/June 2026 Results Announced/)).not.toBeInTheDocument()
  })
})
