import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { chapterActivities } from '../lib/rules'
import { LogActions } from './LogActions'

const counts = (practice: number, revision: number, mock: number, t = { practice: 2, revisions: 2, mocks: 1 }) =>
  chapterActivities({ practice_count: practice, revision_count: revision, mock_count: mock, targets: t })

describe('LogActions', () => {
  it('shows the form with a full activity disabled and explained', () => {
    render(<LogActions activities={counts(0, 0, 2)} onLog={() => {}} />)
    const disabled = document.querySelector('option:disabled')
    expect(disabled?.textContent).toMatch(/Mock test.*all logged/i)
    expect(screen.getByText(/You have logged all 1 mock tests for this chapter/)).toBeInTheDocument()
  })

  it('swaps the form for a done state when every target is reached', () => {
    render(<LogActions activities={counts(2, 2, 1)} onLog={() => {}} />)
    expect(screen.queryByRole('button', { name: /log it/i })).not.toBeInTheDocument()
    expect(screen.getByText(/all logged|everything/i)).toBeInTheDocument()
  })
})
