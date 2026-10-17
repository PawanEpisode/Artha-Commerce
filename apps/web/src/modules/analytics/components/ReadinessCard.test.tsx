import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ReadinessData } from '../lib/types'
import { ReadinessCard } from './ReadinessCard'

describe('ReadinessCard', () => {
  it('renders readiness score and levers when state is ready', () => {
    const mockData: ReadinessData = {
      state: 'ready',
      score: 74.5,
      half_width: 5.2,
      confidence: 'high',
      label: 'Solid',
      components: [
        {
          key: 'accuracy',
          label: 'Mastery Accuracy',
          value: 0.78,
          weight: 0.4,
          points: 31.2,
          available: true,
        },
      ],
      levers: [
        {
          action: 'practice',
          impact_points: 3.5,
          target_type: 'chapter',
          target_id: 'chap-1',
          target_name: 'Direct Tax Salaries',
        },
      ],
      missing_gates: [],
    }

    render(<ReadinessCard data={mockData} isLoading={false} />)

    expect(screen.getByText('Exam Readiness Score')).toBeInTheDocument()
    expect(screen.getByText('74.5')).toBeInTheDocument()
    expect(screen.getByText('(±5.2 band)')).toBeInTheDocument()
    expect(screen.getByText('Direct Tax Salaries')).toBeInTheDocument()
    expect(screen.getByText('+3.5 pts')).toBeInTheDocument()
  })

  it('renders sparse data warning badge when state is sparse', () => {
    const mockData: ReadinessData = {
      state: 'sparse',
      score: null,
      half_width: null,
      confidence: null,
      label: null,
      components: [],
      levers: [],
      missing_gates: ['Need at least 30 questions'],
    }

    render(<ReadinessCard data={mockData} isLoading={false} />)

    expect(screen.getByText('Sparse data')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
