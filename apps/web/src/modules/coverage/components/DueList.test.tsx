import { render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { DueRow } from '../lib/types'
import { DueList } from './DueList'

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, className }: { children: ReactNode; to: string; className?: string }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}))

const due = (n: number, name: string): DueRow =>
  ({
    id: `c${n}`,
    key: `ch-${n}`,
    name,
    coverage_pct: 40,
    confidence: null,
    overdue_days: 0,
    subject: { id: 's1', key: 'tax', name: 'Taxation' },
  }) as unknown as DueRow

describe('the revision list', () => {
  it('hangs another module’s action under each row, outside the row link, with the chapter it belongs to', () => {
    render(
      <DueList
        rows={[due(1, 'GST and ITC'), due(2, 'Income heads')]}
        renderAction={({ chapterId, chapterName }) => <a href={`/x/${chapterId}`}>Do it for {chapterName}</a>}
      />,
    )
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(2)
    const action = within(items[0]).getByRole('link', { name: 'Do it for GST and ITC' })
    expect(action).toHaveAttribute('href', '/x/c1')
    // never a link inside a link
    expect(action.closest('a')).toBe(action)
    expect(within(items[1]).getByRole('link', { name: 'Do it for Income heads' })).toBeInTheDocument()
  })

  it('shows no action without a slot', () => {
    render(<DueList rows={[due(1, 'GST and ITC')]} />)
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })

  it('keeps its empty state', () => {
    render(<DueList rows={[]} renderAction={() => <a href="/x">x</a>} />)
    expect(screen.getByText('Nothing due for revision')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'x' })).not.toBeInTheDocument()
  })
})
