import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  navigate: vi.fn(),
  mutateAsync: vi.fn(),
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
      is_active: false,
      firm_name: '',
      study_mode: 'active_study',
      weekday_minutes: 120,
      weekend_minutes: 360,
      exam_leave_start_date: null,
      target_groups: [],
    },
    exemptions: [],
    available_transitions: [
      {
        type: 'full_level_pass',
        target_level_code: 'final',
        target_level_name: 'Final',
        label: 'Promote to CMA Final',
        description: 'Graduate to Final and archive Intermediate.',
      },
    ],
    current_groups: [
      {
        key: 'group-1',
        name: 'Group 1',
        papers: [
          {
            id: 'p-1',
            key: 'taxation',
            paper_number: 7,
            name: 'Direct and Indirect Taxation',
            total_marks: 100,
            is_excluded: false,
          },
        ],
      },
      {
        key: 'group-2',
        name: 'Group 2',
        papers: [
          {
            id: 'p-2',
            key: 'corporate-law',
            paper_number: 6,
            name: 'Corporate and Economic Laws',
            total_marks: 100,
            is_excluded: false,
          },
        ],
      },
    ],
    result_prompt: {
      should_prompt: true,
      term_name: 'June 2026',
      level_name: 'Intermediate',
    },
  },
}))

vi.mock('@tanstack/react-router', async () => {
  const stub = (await import('~/test/router-stub')).routerStub
  return { ...stub, useNavigate: () => state.navigate }
})

vi.mock('../hooks/useProgression', () => ({
  useProgressionStatus: () => ({ data: state.status, isLoading: false }),
  useTransitionMutation: () => ({
    mutateAsync: state.mutateAsync,
    isPending: false,
  }),
}))

import { ProgressionWizardContainer } from './ProgressionWizardContainer'

describe('ProgressionWizardContainer', () => {
  beforeEach(() => {
    state.navigate.mockReset()
    state.mutateAsync.mockReset()
    state.mutateAsync.mockResolvedValue({
      transition_id: 'trans-1',
      status: 'applied',
      new_enrollment_id: 'enr-2',
      message: 'Congratulations on clearing CMA Intermediate! Welcome to CMA Final.',
    })
  })

  it('navigates through wizard steps and handles 60+ marks exemption feedback', async () => {
    render(<ProgressionWizardContainer />)

    // Step 1: Outcome Selection
    expect(screen.getByText('Cleared Level Completely')).toBeInTheDocument()
    expect(screen.getByText('Cleared Group(s)')).toBeInTheDocument()
    expect(screen.getByText('Paper Exemptions')).toBeInTheDocument()

    // Select Full Level Pass
    fireEvent.click(screen.getByText('Cleared Level Completely'))

    // Step 2: Configuration
    expect(screen.getByText(/Next Tier: FINAL/)).toBeInTheDocument()
    expect(screen.getByText('Direct and Indirect Taxation')).toBeInTheDocument()

    // Enter 68 marks for Taxation -> Should trigger Golden Exemption badge
    const marksInputs = screen.getAllByLabelText('Marks:')
    fireEvent.change(marksInputs[0], { target: { value: '68' } })

    expect(screen.getByText(/Official 60\+ Exemption Granted!/)).toBeInTheDocument()
    expect(screen.getByText('Make Permanent')).toBeInTheDocument()

    // Proceed to Step 3: Routine & Articleship
    fireEvent.click(screen.getByText('Continue to Routine Setup'))

    expect(screen.getByText(/Are you currently in Practical Training/)).toBeInTheDocument()

    // Toggle Articleship ON
    const articleshipSwitch = screen.getByLabelText('Toggle articleship status')
    fireEvent.click(articleshipSwitch)

    expect(screen.getByLabelText(/Firm \/ Employer Name/)).toBeInTheDocument()
    expect(screen.getByText('Active Study (Balanced)')).toBeInTheDocument()
    expect(screen.getByText('Weekend Warrior')).toBeInTheDocument()

    // Proceed to Step 4: Review
    fireEvent.click(screen.getByText('Review Transformation'))

    expect(screen.getByText('Review & Instant Workspace Calibration')).toBeInTheDocument()
    expect(screen.getByText('Workspace Transformation Overview')).toBeInTheDocument()

    // Submit Transition
    const confirmButton = screen.getByText('Confirm & Launch Workspace')
    fireEvent.click(confirmButton)

    expect(state.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        transition_type: 'full_level_pass',
        target_level_code: 'final',
        paper_results: [
          expect.objectContaining({
            subject_key: 'taxation',
            marks: 68,
            status: 'exempted',
          }),
        ],
        articleship: expect.objectContaining({
          is_active: true,
        }),
      }),
    )
  })
})
