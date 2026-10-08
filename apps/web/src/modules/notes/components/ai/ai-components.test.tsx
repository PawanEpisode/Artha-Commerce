import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { SummaryJob } from '../../lib/ai-types'
import { ConsentPanel } from './ConsentPanel'
import { SummaryDraftView } from './SummaryDraftView'
import { SummaryOffer } from './SummaryOffer'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('~/lib/richtext', () => ({ RichText: ({ markdown }: { markdown: string }) => <div>{markdown}</div> }))

const text = {
  version: 'v1',
  title: 'Use AI help',
  points: [{ heading: 'What is sent', text: 'Your notes.' }],
  checkbox: 'I agree.',
}
const job = (over: Partial<SummaryJob> = {}): SummaryJob => ({
  id: 'j1',
  kind: 'exam_summary',
  status: 'ready',
  chapter: { chapter_id: 'c1', level_id: null, subject_key: null, chapter_key: null },
  item_count: 4,
  estimate_seconds: 30,
  cached: false,
  error_code: null,
  charged: true,
  created_at: '2026-10-08T00:00:00Z',
  finished_at: null,
  expires_at: null,
  draft: {
    title: 'GST summary',
    body_md: '# GST\n\n- Point [1]\n\n## Sources\n1. n',
    sources: [{ n: 1, kind: 'note', id: 'n1', page: null, document_id: null, label: 'My GST note' }],
    dropped: 2,
  },
  result_note_id: null,
  ...over,
})
const handlers = {
  busy: false,
  failed: false,
  onAccept: vi.fn(),
  onEdit: vi.fn(),
  onDiscard: vi.fn(),
  onCancel: vi.fn(),
}

describe('ConsentPanel', () => {
  it('keeps Agree off until the box is ticked, and Not now sends nothing', async () => {
    const onAgree = vi.fn()
    const onCancel = vi.fn()
    render(<ConsentPanel text={text} pending={false} failed={false} onAgree={onAgree} onCancel={onCancel} />)
    const agree = screen.getByRole('button', { name: /Agree and continue/ })
    expect(agree).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(agree)
    expect(onAgree).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

describe('SummaryDraftView', () => {
  it('labels the draft as AI, hides the Sources heading in the text and lists sources with links', () => {
    render(<SummaryDraftView job={job()} {...handlers} />)
    expect(screen.getByText('AI draft, check against the material')).toBeInTheDocument()
    expect(screen.queryByText(/## Sources/)).toBeNull()
    expect(screen.getByRole('link', { name: 'My GST note' })).toHaveAttribute('href', '/app/notes/n/n1')
    expect(screen.getByText(/2 points/)).toBeInTheDocument()
  })

  it('offers save, edit and discard on a ready draft', async () => {
    const onAccept = vi.fn()
    const onDiscard = vi.fn()
    render(<SummaryDraftView job={job()} {...handlers} onAccept={onAccept} onDiscard={onDiscard} />)
    await userEvent.click(screen.getByRole('button', { name: /Save to my notes/ }))
    await userEvent.click(screen.getByRole('button', { name: /Discard/ }))
    expect(onAccept).toHaveBeenCalled()
    expect(onDiscard).toHaveBeenCalled()
  })

  it('shows progress with a cancel while the job is waiting', async () => {
    const onCancel = vi.fn()
    render(<SummaryDraftView job={job({ status: 'running', draft: null })} {...handlers} onCancel={onCancel} />)
    expect(screen.getByRole('status')).toHaveTextContent(/Writing your summary/)
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('says nothing was charged when it failed, and links to the note once saved', () => {
    const { rerender } = render(
      <SummaryDraftView job={job({ status: 'failed', draft: null, error_code: 'model_error' })} {...handlers} />,
    )
    expect(screen.getByText(/Nothing was used from your allowance/)).toBeInTheDocument()
    rerender(<SummaryDraftView job={job({ status: 'accepted', result_note_id: 'n9' })} {...handlers} />)
    expect(screen.getByRole('link', { name: 'Open the note' })).toHaveAttribute('href', '/app/notes/n/n9')
  })
})

describe('SummaryOffer', () => {
  it('invites a new summary, or returns to the one in progress', () => {
    const { rerender } = render(<SummaryOffer chapterId="c1" job={null} />)
    expect(screen.getByRole('link', { name: 'Write a summary' })).toBeInTheDocument()
    rerender(<SummaryOffer chapterId="c1" job={job()} />)
    expect(screen.getByRole('link', { name: 'Review the draft' })).toHaveAttribute('href', '/app/notes/summary/j1')
  })
})
