import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ContinueChapter, DueRow } from '~/modules/coverage'

import { ContinueView } from './ContinueView'
import { DueView } from './DueView'
import { SetupCards } from './SetupCards'
import { TodayView } from './TodayView'
import { WidgetCard } from './WidgetCard'

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, to, ...rest }: { children: React.ReactNode; to: string; params?: unknown; search?: unknown }) => (
    <a href={to} className={(rest as { className?: string }).className}>
      {children}
    </a>
  ),
}))

describe('WidgetCard', () => {
  it('draws a labelled skeleton while loading, with no content', () => {
    render(
      <WidgetCard id="w" title="Today" state="loading">
        <p>content</p>
      </WidgetCard>,
    )
    expect(screen.getByRole('status', { name: 'Loading Today' })).toBeInTheDocument()
    expect(screen.queryByText('content')).toBeNull()
  })

  it('shows an error with Retry that calls back, and keeps its heading', async () => {
    const retry = vi.fn()
    render(
      <WidgetCard id="w" title="Today" state="error" onRetry={retry}>
        <p>content</p>
      </WidgetCard>,
    )
    expect(screen.getByRole('heading', { name: 'Today' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(retry).toHaveBeenCalledOnce()
  })

  it('shows the offline badge only over ready content', () => {
    const { rerender } = render(
      <WidgetCard id="w" title="Today" state="ready" offline>
        <p>content</p>
      </WidgetCard>,
    )
    expect(screen.getByText('Offline')).toBeInTheDocument()
    rerender(
      <WidgetCard id="w" title="Today" state="loading" offline>
        <p>content</p>
      </WidgetCard>,
    )
    expect(screen.queryByText('Offline')).toBeNull()
  })
})

describe('TodayView', () => {
  it('states the numbers in text and offers the primary action and Log time', () => {
    render(
      <TodayView
        percent={58}
        doneLabel="1 h 10 m of 2 h"
        streak={6}
        action={{ kind: 'start', to: '/app/focus', label: 'Start focus round' }}
        canLogTime
      />,
    )
    expect(screen.getByText('1 h 10 m of 2 h')).toBeInTheDocument()
    expect(screen.getByText('6 day streak')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start focus round' })).toHaveAttribute('href', '/app/focus')
    expect(screen.getByRole('link', { name: 'Log time' })).toBeInTheDocument()
  })
  it('says "1 day streak" and drops the primary action when none applies', () => {
    render(<TodayView percent={0} doneLabel="0 m of 2 h" streak={1} action={{ kind: 'none' }} canLogTime={false} />)
    expect(screen.getByText('1 day streak')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })
})

const chapter = {
  id: 'c1',
  name: 'Cost Sheet',
  coverage_pct: 42,
  subject: { id: 's1', key: 'cost', name: 'Cost Accounting' },
} as ContinueChapter

describe('ContinueView', () => {
  it('shows the chapter with its percent and a Continue link', () => {
    render(<ContinueView chapter={chapter} />)
    expect(screen.getByText('42% covered')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Continue/ })).toBeInTheDocument()
  })
  it('opens the syllabus map on day one and offers the last page when there is one', async () => {
    const back = vi.fn()
    render(<ContinueView chapter={null} onReturn={back} />)
    expect(screen.getByRole('link', { name: /Open the syllabus map/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Return to your last page' }))
    expect(back).toHaveBeenCalledOnce()
  })
})

describe('DueView', () => {
  const row = (n: number, late: number) =>
    ({ id: `r${n}`, name: `Chapter ${n}`, overdue_days: late, subject: { id: 's', key: 'k', name: 'Paper' } }) as DueRow
  it('lists chapters with how late they are and links to the rest', () => {
    render(<DueView rows={[row(1, 2), row(2, 0)]} total={5} />)
    expect(screen.getByText('2 days late')).toBeInTheDocument()
    expect(screen.getByText('Due today')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'See all 5 due' })).toBeInTheDocument()
  })
  it('has no "see all" when everything is shown', () => {
    render(<DueView rows={[row(1, 1)]} total={1} />)
    expect(screen.queryByRole('link', { name: /See all/ })).toBeNull()
  })
})

describe('SetupCards', () => {
  it('gives each skipped step a way back in and a way to hide it', async () => {
    const hide = vi.fn()
    render(
      <SetupCards cards={[{ key: 'avatar', title: 'Add a photo', description: 'Choose one.' }]} onDismiss={hide} />,
    )
    expect(screen.getByRole('link', { name: /Finish Add a photo/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Hide Add a photo' }))
    expect(hide).toHaveBeenCalledWith('avatar')
  })
})
