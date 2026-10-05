import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { ChapterRow } from '../lib/types'
import { ChapterList } from './ChapterList'

// The list only needs links to render; the router itself is not under test here.
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, className }: { children: ReactNode; to: string; className?: string }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

const row = (n: number, name: string, over: Partial<ChapterRow> = {}): ChapterRow => ({
  id: `c${n}`,
  key: `ch-${n}`,
  name,
  section: '',
  marks_min: null,
  marks_max: null,
  marks_weight: 0,
  has_topics: false,
  topics_total: 0,
  topics_done: 0,
  coverage_pct: 0,
  status: 'not_started',
  confidence: null,
  is_excluded: false,
  components: { read: 0, practice: 0, revise: 0, mock: 0 },
  practice_count: 0,
  mock_count: 0,
  revision_count: 0,
  targets: { practice: 0, revisions: 0, mocks: 0 },
  total_study_seconds: 0,
  last_studied_at: null,
  last_revised_at: null,
  next_revision_due: null,
  ...over,
})

const NAMES = [
  'Income from Salaries',
  'Income from House Property',
  'Profits and Gains of Business',
  'Capital Gains',
  'Income from Other Sources',
  'Clubbing of Income',
  'Set Off and Carry Forward of Losses',
  'Deductions under Chapter VI-A',
  'Computation of Total Income',
  'Advance Tax and TDS',
]

const many = NAMES.map((n, i) => row(i + 1, n, i === 0 ? { status: 'reading', coverage_pct: 40 } : {}))
const items = () => screen.getAllByRole('listitem')

describe('ChapterList search', () => {
  it('offers the search only when the paper is long enough to need it', () => {
    render(<ChapterList subjectId="s1" chapters={many.slice(0, 3)} />)
    expect(screen.queryByRole('searchbox', { name: 'Find a chapter' })).not.toBeInTheDocument()
  })

  it('filters by name, ignoring case, and says how many match', async () => {
    render(<ChapterList subjectId="s1" chapters={many} />)
    expect(items()).toHaveLength(10)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Find a chapter' }), 'INCOME FROM')
    expect(items()).toHaveLength(3)
    expect(screen.getByText('3 chapters of 10 match')).toBeInTheDocument()
    expect(within(items()[0]!).getByText('Income from Salaries')).toBeInTheDocument()
  })

  it('keeps each chapter’s own number while filtered', async () => {
    render(<ChapterList subjectId="s1" chapters={many} />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Find a chapter' }), 'capital gains')
    expect(items()).toHaveLength(1)
    expect(within(items()[0]!).getByText('4')).toBeInTheDocument()
  })

  it('says so when nothing matches, and restores the list when cleared', async () => {
    render(<ChapterList subjectId="s1" chapters={many} />)
    const box = screen.getByRole('searchbox', { name: 'Find a chapter' })
    await userEvent.type(box, 'zzz')
    expect(screen.getByText('No chapter matches.')).toBeInTheDocument()
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    await userEvent.clear(box)
    expect(items()).toHaveLength(10)
  })

  it('combines the search with "only chapters I have not started"', async () => {
    render(<ChapterList subjectId="s1" chapters={many} />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Find a chapter' }), 'income from')
    await userEvent.click(screen.getByRole('switch', { name: /not started/ }))
    expect(items()).toHaveLength(2)
    expect(screen.queryByText('Income from Salaries')).not.toBeInTheDocument()
  })
})
