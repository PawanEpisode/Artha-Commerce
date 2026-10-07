import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { HighlightRow as Row } from '../../lib/library-types'
import { emptyRow } from '../../lib/page-ranges'
import { UNFILED_LINK } from '../../lib/testing'
import { makeDocument } from '../../lib/testing-documents'
import { ChapterNotesCard } from '../ChapterNotesCard'
import { ChapterRows } from '../ChapterRows'
import { FilterBar } from '../FilterBar'
import { HighlightRow } from './HighlightRow'
import { PageRangeEditor } from './PageRangeEditor'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const legend = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }
const mark = (over: Partial<Row> = {}): Row => ({
  type: 'highlight',
  id: 'm1',
  document_id: 'doc-1',
  page: 14,
  kind: 'highlight',
  color: 'g',
  comment: '',
  quote_exact: 'Credit on motor vehicles is blocked',
  link: UNFILED_LINK,
  tags: [{ id: 't1', name: 'revise', color_key: null }] as never,
  recall_card_id: null,
  updated_at: '2026-10-01T00:00:00Z',
  ...over,
})

describe('HighlightRow', () => {
  it('shows the text, the colour NAME, the document and page, and opens at the mark', () => {
    render(<HighlightRow row={mark()} colorName="Formula" documentTitle="Taxation module" />)
    expect(screen.getByRole('link', { name: /Credit on motor vehicles is blocked/ })).toHaveAttribute(
      'href',
      '/app/notes/pdf/doc-1?page=14&ann=m1',
    )
    expect(screen.getByText('Formula')).toBeInTheDocument()
    expect(screen.getByText('Taxation module · page 14')).toBeInTheDocument()
    expect(screen.getByText('revise')).toBeInTheDocument()
  })

  it('badges a mark that became a recall card, and a chapter that moved', () => {
    render(
      <HighlightRow
        row={mark({ recall_card_id: 'c1', link: { ...UNFILED_LINK, moved_or_removed: true } })}
        documentTitle="Taxation module"
      />,
    )
    expect(screen.getByText('Card')).toBeInTheDocument()
    expect(screen.getByText('Chapter moved or removed')).toBeInTheDocument()
  })

  it('falls back to the comment, then to the kind, for a mark with no quote', () => {
    const { rerender } = render(
      <HighlightRow row={mark({ quote_exact: null, comment: 'Check with sir', kind: 'sticky' })} />,
    )
    expect(screen.getByRole('link', { name: /Check with sir/ })).toBeInTheDocument()
    rerender(<HighlightRow row={mark({ quote_exact: null, comment: '', kind: 'area' })} />)
    expect(screen.getByRole('link', { name: /Area highlight on page 14/ })).toBeInTheDocument()
  })
})

describe('FilterBar for marks', () => {
  const docs = [{ id: 'doc-1', title: 'Taxation module' }]
  it('offers Highlights and Documents tabs, and colour by legend name, only when PDFs are on', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<FilterBar search={{}} tags={[]} onChange={onChange} />)
    expect(screen.queryByRole('radio', { name: 'Highlights' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Colour')).not.toBeInTheDocument()
    rerender(<FilterBar search={{}} tags={[]} legend={legend} documents={docs} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Highlights' }))
    expect(onChange).toHaveBeenCalledWith({ tab: 'highlights', cursor: undefined })
    expect(screen.getByLabelText('Colour')).toBeInTheDocument()
    expect(screen.getByLabelText('Document')).toBeInTheDocument()
  })

  it('shows colour and document as chips with names, never the colour key', async () => {
    const onChange = vi.fn()
    render(
      <FilterBar
        search={{ tab: 'highlights', color: 'g', doc: 'doc-1' }}
        tags={[]}
        legend={legend}
        documents={docs}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('Colour: Formula')).toBeInTheDocument()
    expect(screen.getByText('Document: Taxation module')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Remove filter Colour: Formula' }))
    expect(onChange).toHaveBeenCalledWith({ tab: 'highlights', doc: 'doc-1' })
  })

  it('hides the colour and document filters on the Notes tab', () => {
    render(
      <FilterBar search={{ tab: 'notes' }} tags={[]} legend={legend} documents={docs} onChange={() => undefined} />,
    )
    expect(screen.queryByLabelText('Colour')).not.toBeInTheDocument()
  })
})

describe('ChapterRows with PDFs', () => {
  const chapter = {
    chapter_id: 'c1',
    chapter_key: 'itc',
    name: 'ITC',
    notes: 2,
    highlights: 12,
    marks: 3,
    documents: 1,
    has_summary: false,
    last_noted_at: null,
  }
  it('counts notes, highlights, marks and PDFs in one line', () => {
    render(<ChapterRows subjectKey="tax" chapters={[chapter]} moved={[]} onRelink={() => undefined} />)
    expect(screen.getByText('2 notes, 12 highlights, 3 marks, 1 PDF')).toBeInTheDocument()
  })
  it('puts marks and PDFs of moved chapters in the "Moved or removed chapters" group', () => {
    render(
      <ChapterRows
        subjectKey="tax"
        chapters={[]}
        moved={[{ chapter_key: 'old', chapter_name: 'Old chapter', notes: 0, highlights: 4, marks: 1, documents: 2 }]}
        onRelink={() => undefined}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Moved or removed chapters' })).toBeInTheDocument()
    expect(screen.getByText('4 highlights, 1 mark, 2 PDFs')).toBeInTheDocument()
  })
  it('says "No notes yet" for an empty chapter', () => {
    render(
      <ChapterRows
        subjectKey="tax"
        chapters={[{ ...chapter, notes: 0, highlights: 0, marks: 0, documents: 0 }]}
        moved={[]}
        onRelink={() => undefined}
      />,
    )
    expect(screen.getByText('No notes yet')).toBeInTheDocument()
  })
})

describe('ChapterNotesCard with PDFs', () => {
  it('lists the PDFs linked to the chapter', () => {
    render(
      <ChapterNotesCard
        state="ready"
        subjectKey="tax"
        chapterKey="itc"
        onRetry={() => undefined}
        overview={{
          chapter: { id: 'c', key: 'itc', name: 'ITC', subject_key: 'tax', subject_name: 'Tax', level_id: 'l' },
          counts: { notes: 0, highlights: 3, marks: 0, documents: 1 },
          has_summary: false,
          last_noted_at: null,
          current_summary: null,
          recent: [],
          documents: [makeDocument({ title: 'Taxation module' })],
        }}
      />,
    )
    expect(screen.getByRole('link', { name: 'Taxation module' })).toHaveAttribute(
      'href',
      expect.stringContaining('/app/notes/pdf/'),
    )
    expect(screen.getByText('1 PDF linked here')).toBeInTheDocument()
  })
})

describe('PageRangeEditor', () => {
  const rows = [
    { ...emptyRow('1'), key: 'a', to: '10', chapterId: 'c1', chapterLabel: 'GST › ITC' },
    { ...emptyRow('8'), key: 'b', to: '20' },
  ]
  const props = {
    rows,
    problems: { b: 'Overlaps pages 1 to 10.' },
    pageCount: 100,
    onEdit: vi.fn(),
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    onPickChapter: vi.fn(),
    onSuggest: vi.fn(),
    dirty: true,
    saving: false,
    onSave: vi.fn(),
    onReset: vi.fn(),
  }
  it('shows an overlap inline on its row and blocks Save', () => {
    render(<PageRangeEditor {...props} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Overlaps pages 1 to 10.')
    expect(screen.getByRole('button', { name: 'Save page ranges' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'GST › ITC for range 1' })).toBeInTheDocument()
  })
  it('adds, suggests from the contents, picks a chapter and removes by keyboard-reachable buttons', async () => {
    const p = { ...props, problems: {}, onAdd: vi.fn(), onSuggest: vi.fn(), onPickChapter: vi.fn() }
    render(<PageRangeEditor {...p} />)
    await userEvent.click(screen.getByRole('button', { name: /Add a range/ }))
    await userEvent.click(screen.getByRole('button', { name: /Start from the contents/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose a chapter for range 2' }))
    expect(p.onAdd).toHaveBeenCalled()
    expect(p.onSuggest).toHaveBeenCalled()
    expect(p.onPickChapter).toHaveBeenCalledWith('b')
    expect(screen.getByRole('button', { name: 'Save page ranges' })).toBeEnabled()
  })
  it('explains an empty set', () => {
    render(<PageRangeEditor {...props} rows={[]} problems={{}} dirty={false} />)
    expect(screen.getByText(/No ranges yet/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save page ranges' })).not.toBeInTheDocument()
  })
})
