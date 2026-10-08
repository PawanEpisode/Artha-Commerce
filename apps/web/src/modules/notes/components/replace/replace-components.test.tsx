import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AttentionItem } from '../../lib/replace-types'
import { AttentionSheet } from './AttentionSheet'
import { ReplaceSection } from './ReplaceSection'

const item = (over: Partial<AttentionItem> = {}): AttentionItem => ({
  id: 'i1',
  source_annotation_id: 'a1',
  kind: 'highlight',
  page: 3,
  color: 'y',
  quote: 'tax credit under GST',
  comment: 'remember',
  reason: 'not_found',
  status: 'open',
  new_annotation_id: null,
  result_note_id: null,
  resolved_at: null,
  ...over,
})

function sheet(over: Partial<React.ComponentProps<typeof AttentionSheet>> = {}) {
  const onResolve = vi.fn()
  render(
    <AttentionSheet
      open
      onOpenChange={() => undefined}
      title="GST notes"
      items={[item()]}
      loading={false}
      failed={false}
      online
      onRetry={() => undefined}
      onResolve={onResolve}
      {...over}
    />,
  )
  return { onResolve }
}

describe('AttentionSheet', () => {
  it('shows the quote, its page and why it was not placed, and sends each decision', async () => {
    const { onResolve } = sheet()
    expect(screen.getByText('tax credit under GST')).toBeInTheDocument()
    expect(screen.getByText(/page 3 of the old edition/)).toBeInTheDocument()
    expect(screen.getByText('These words are not in the new edition.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Keep on page 3/ }))
    await userEvent.click(screen.getByRole('button', { name: /Save as a note/ }))
    await userEvent.click(screen.getByRole('button', { name: /Dismiss/ }))
    expect(onResolve.mock.calls.map((c) => c[1])).toEqual(['keep', 'note', 'dismiss'])
  })

  it('hides "Save as a note" for a mark with nothing to save and disables decisions offline', () => {
    sheet({ items: [item({ quote: '', comment: '' })], online: false })
    expect(screen.queryByRole('button', { name: /Save as a note/ })).toBeNull()
    expect(screen.getByRole('button', { name: /Keep on page 3/ })).toBeDisabled()
  })

  it('shows what was decided instead of the buttons', () => {
    sheet({ items: [item({ status: 'noted' })] })
    expect(screen.getByText('Saved as a note')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Dismiss/ })).toBeNull()
  })

  it('shows a loading state', () => {
    sheet({ loading: true, items: [] })
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull()
  })

  it('offers Try again when loading failed', async () => {
    const onRetry = vi.fn()
    sheet({ failed: true, items: [], onRetry })
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('says so when nothing is waiting', () => {
    sheet({ items: [] })
    expect(screen.getByText(/Nothing is waiting/)).toBeInTheDocument()
  })
})

describe('ReplaceSection', () => {
  const base = { statusText: null, working: false, openCount: 0, canReplace: true, online: true }

  it('offers the replacement and calls it', async () => {
    const onReplace = vi.fn()
    render(<ReplaceSection {...base} onReview={() => undefined} onReplace={onReplace} />)
    await userEvent.click(screen.getByRole('button', { name: /Replace with a newer edition/ }))
    expect(onReplace).toHaveBeenCalled()
  })

  it('shows progress and the review button with the count', async () => {
    const onReview = vi.fn()
    render(
      <ReplaceSection
        {...base}
        statusText="Moving your marks to this edition…"
        working
        openCount={2}
        canReplace={false}
        onReview={onReview}
        onReplace={() => undefined}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Moving your marks')
    await userEvent.click(screen.getByRole('button', { name: 'Review 2 marks' }))
    expect(onReview).toHaveBeenCalled()
  })

  it('renders nothing when there is nothing to say or do', () => {
    const { container } = render(
      <ReplaceSection {...base} canReplace={false} onReview={() => undefined} onReplace={() => undefined} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
