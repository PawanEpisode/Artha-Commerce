import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  rollbackMutateAsync: vi.fn(),
  status: {
    active_enrollment: {
      id: 'enr-1',
      course_code: 'cma',
      course_name: 'CMA',
      level_code: 'intermediate',
      level_name: 'Intermediate',
      scheme_id: 'sch-1',
      scheme_name: '2022 Scheme',
      term_code: '2026-06',
      term_name: 'June 2026',
      exam_date: '2026-06-10',
      daily_minutes: 360,
    },
    articleship: {
      is_active: true,
      firm_name: 'Deloitte India',
      study_mode: 'active_study',
      weekday_minutes: 120,
      weekend_minutes: 360,
      exam_leave_start_date: null,
      target_groups: ['group-2'],
    },
    exemptions: [
      {
        id: 'ex-1',
        subject_id: 'sub-tax',
        subject_name: 'Direct and Indirect Taxation',
        paper_number: 7,
        marks_obtained: 68,
        granted_term_code: '2025-12',
        valid_until_term_code: '2027-06',
        is_permanent: false,
        is_exhausted: false,
        granted_at: '2026-01-15T00:00:00Z',
      },
    ],
    available_transitions: [],
    current_groups: [],
  },
  history: {
    history: [
      {
        id: 'tr-1',
        transition_type: 'group_clearance',
        trigger: 'user_initiated',
        status: 'applied',
        effective_date: '2026-01-15T10:00:00Z',
        created_at: '2026-01-15T10:00:00Z',
        can_rollback: true,
        from_level: { course_code: 'cma', level_code: 'intermediate', level_name: 'Intermediate' },
        to_level: { course_code: 'cma', level_code: 'intermediate', level_name: 'Intermediate' },
        paper_results: [
          {
            subject_key: 'taxation',
            status: 'exempted',
            marks_obtained: 68,
            is_carry_forward: true,
          },
        ],
        metadata: {},
      },
    ],
  },
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, className }: { children: React.ReactNode; to: string; className?: string }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

vi.mock('../hooks/useProgression', () => ({
  useProgressionStatus: () => ({
    data: state.status,
    isLoading: false,
  }),
  useTransitionHistory: () => ({
    data: state.history,
    isLoading: false,
  }),
  useRollbackMutation: () => ({
    mutateAsync: state.rollbackMutateAsync,
    isPending: false,
  }),
}))

import { ProgressionSettingsContainer } from './ProgressionSettingsContainer'

describe('ProgressionSettingsContainer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders active level, exemptions, articleship summary, and transition history', () => {
    render(<ProgressionSettingsContainer />)

    expect(screen.getByText('Progression & Exemptions')).toBeInTheDocument()
    expect(screen.getByText('CMA • Intermediate')).toBeInTheDocument()
    expect(screen.getByText(/Deloitte India/)).toBeInTheDocument()
    expect(screen.getByText('Direct and Indirect Taxation')).toBeInTheDocument()
    expect(screen.getByText('68')).toBeInTheDocument()
    expect(screen.getByText('group clearance')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Undo \(48h\)/i })).toBeInTheDocument()
  })

  it('triggers rollback confirmation dialog and mutates rollback on confirm', async () => {
    render(<ProgressionSettingsContainer />)

    const undoBtn = screen.getByRole('button', { name: /Undo \(48h\)/i })
    expect(undoBtn).toBeInTheDocument()
    fireEvent.click(undoBtn)

    expect(screen.getByText('Undo Level Transition?')).toBeInTheDocument()
    expect(screen.getByText(/This will re-activate your previous level syllabus/)).toBeInTheDocument()

    const confirmRollbackBtn = screen.getByRole('button', { name: 'Confirm Rollback' })
    fireEvent.click(confirmRollbackBtn)

    expect(state.rollbackMutateAsync).toHaveBeenCalledWith('tr-1')
  })
})
