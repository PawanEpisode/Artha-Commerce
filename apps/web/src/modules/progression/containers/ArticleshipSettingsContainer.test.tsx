import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  articleship: {
    is_active: true,
    firm_name: 'KPMG India',
    registration_number: 'ART-99201',
    training_start_date: '2025-01-01',
    expected_completion_date: '2027-01-01',
    study_mode: 'active_study',
    weekday_minutes: 120,
    weekend_minutes: 360,
    exam_leave_start_date: '2026-04-01',
    target_groups: [],
  },
}))

vi.mock('../hooks/useProgression', () => ({
  useArticleship: () => ({
    data: state.articleship,
    isLoading: false,
  }),
  useArticleshipMutation: () => ({
    mutateAsync: state.mutateAsync,
    isPending: false,
  }),
}))

import { ArticleshipSettingsContainer } from './ArticleshipSettingsContainer'

describe('ArticleshipSettingsContainer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders articleship settings and switches study modes', () => {
    render(<ArticleshipSettingsContainer />)

    expect(screen.getByText('Articleship & Practical Training Planner')).toBeInTheDocument()
    expect(screen.getByDisplayValue('KPMG India')).toBeInTheDocument()
    expect(screen.getByText('Active Study (Balanced)')).toBeInTheDocument()
    expect(screen.getByText('Weekend Warrior')).toBeInTheDocument()
    expect(screen.getByText('Work-Focus Pause')).toBeInTheDocument()

    // Switch mode to Weekend Warrior
    const weekendWarriorCard = screen.getByText('Weekend Warrior')
    fireEvent.click(weekendWarriorCard)

    // Check weekday and weekend values updated: 30m weekday and 420m (7.0 hrs) weekend
    expect(screen.getByText('0.5 hrs (30m)')).toBeInTheDocument()
    expect(screen.getByText('7.0 hrs (420m)')).toBeInTheDocument()

    // Save configuration
    const saveBtn = screen.getByRole('button', { name: 'Save Articleship Schedule' })
    fireEvent.click(saveBtn)

    expect(state.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        is_active: true,
        firm_name: 'KPMG India',
        study_mode: 'weekend_only',
        weekday_minutes: 30,
        weekend_minutes: 420,
      }),
    )
  })

  it('allows toggling articleship off and saving', () => {
    render(<ArticleshipSettingsContainer />)

    const toggle = screen.getByLabelText('Toggle active articleship')
    fireEvent.click(toggle)

    const saveBtn = screen.getByRole('button', { name: 'Save Articleship Schedule' })
    fireEvent.click(saveBtn)

    expect(state.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        is_active: false,
      }),
    )
  })
})
