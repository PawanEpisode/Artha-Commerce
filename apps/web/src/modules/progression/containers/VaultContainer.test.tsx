import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  vaultData: {
    enrollments: [
      {
        enrollment_id: 'enr-vault-1',
        course_code: 'cma',
        course_name: 'CMA',
        level_code: 'intermediate',
        level_name: 'Intermediate',
        scheme_name: '2022 Scheme',
        term_name: 'Dec 2025',
        exam_date: '2025-12-10',
        notes_count: 42,
        docs_count: 15,
        subjects: [
          {
            key: 'taxation',
            paper_number: 7,
            name: 'Direct and Indirect Taxation',
          },
          {
            key: 'cost-acct',
            paper_number: 8,
            name: 'Cost Accounting',
          },
        ],
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
  useVaultEnrollments: () => ({
    data: state.vaultData,
    isLoading: false,
  }),
}))

import { VaultContainer } from './VaultContainer'

describe('VaultContainer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders preserved levels with notes count, documents count, and subject papers', () => {
    render(<VaultContainer />)

    expect(screen.getByText('Past Level Vault')).toBeInTheDocument()
    expect(screen.getByText('Intermediate')).toBeInTheDocument()
    expect(screen.getByText('42 Notes')).toBeInTheDocument()
    expect(screen.getByText('15 Documents')).toBeInTheDocument()
    expect(screen.getByText('Direct and Indirect Taxation')).toBeInTheDocument()
    expect(screen.getByText('Cost Accounting')).toBeInTheDocument()
  })

  it('filters preserved subjects based on search query', () => {
    render(<VaultContainer />)

    const searchInput = screen.getByPlaceholderText('Search past subjects or notes...')
    fireEvent.change(searchInput, { target: { value: 'Taxation' } })

    expect(screen.getByText('Direct and Indirect Taxation')).toBeInTheDocument()

    fireEvent.change(searchInput, { target: { value: 'NonExistentSubject' } })
    expect(screen.getByText('No matching subjects found')).toBeInTheDocument()
  })
})
