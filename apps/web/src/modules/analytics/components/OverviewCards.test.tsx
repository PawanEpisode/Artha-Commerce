import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OverviewCards } from './OverviewCards'

describe('OverviewCards', () => {
  it('renders skeleton loaders when loading', () => {
    const { container } = render(<OverviewCards isLoading={true} />)
    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(4)
  })

  it('renders metric cards accurately with provided data', () => {
    const mockData = {
      total_answered: 142,
      total_correct: 110,
      overall_accuracy: 0.775,
      overall_accuracy_pct: 78,
      study_seconds: 7200,
      study_hours_formatted: '2h 0m',
      coverage_percentage: 64,
      days_active: 12,
      facts_version: 1,
      last_calculated_at: '2026-10-17T12:00:00Z',
    }

    render(<OverviewCards data={mockData} isLoading={false} />)

    expect(screen.getByText('142')).toBeInTheDocument()
    expect(screen.getByText('78%')).toBeInTheDocument()
    expect(screen.getByText('2h 0m')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })
})
