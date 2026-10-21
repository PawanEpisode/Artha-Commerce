import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { TodayHomeRedirect } from './TodayHomeRedirect'

describe('TodayHomeRedirect', () => {
  it('renders children directly without redirecting', () => {
    render(
      <TodayHomeRedirect>
        <div>Workspace Home Content</div>
      </TodayHomeRedirect>,
    )
    expect(screen.getByText('Workspace Home Content')).toBeInTheDocument()
  })
})
