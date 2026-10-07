import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { MarkSearchHit, PdfSearchHit } from '../../lib/library-types'
import { groupPdfHits, notSearchable } from '../../lib/search-groups'
import { UNFILED_LINK } from '../../lib/testing'
import { MarkResults, PdfResultGroups, PdfSearchNotices } from './PdfSearchResults'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const hit = (document_id: string, page: number, rank: number, snippet: string): PdfSearchHit => ({
  type: 'pdf',
  document_id,
  document_title: document_id === 'a' ? 'Taxation module' : 'Law module',
  page,
  snippet,
  rank,
  link: UNFILED_LINK,
})
const legend = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }

describe('PdfResultGroups', () => {
  it('groups by document, marks the matching words and opens the page with the query', () => {
    const groups = groupPdfHits([
      hit('a', 14, 1, 'input tax credit is blocked'),
      hit('a', 20, 2, 'credit notes'),
      hit('b', 3, 3, 'credit'),
    ])
    render(<PdfResultGroups groups={groups} query="credit" />)
    const first = screen.getByRole('heading', { name: 'Taxation module' }).closest('li') as HTMLElement
    expect(
      within(first)
        .getAllByText('credit')
        .every((el) => el.tagName === 'MARK'),
    ).toBe(true)
    const open = within(first).getByRole('link', { name: /Open page 14/ })
    expect(open).toHaveAttribute('href', '/app/notes/pdf/a?page=14&q=credit')
    expect(screen.getByRole('heading', { name: 'Law module' })).toBeInTheDocument()
  })

  it('says how many more pages a document has beyond the five shown', () => {
    const many = Array.from({ length: 8 }, (_, i) => hit('a', i + 1, i, 'credit'))
    render(<PdfResultGroups groups={groupPdfHits(many)} query="credit" />)
    expect(screen.getAllByRole('link', { name: /Open page/ })).toHaveLength(5)
    expect(screen.getByText(/and 3 more pages in this document/)).toBeInTheDocument()
  })

  it('calls onOpen when a result is opened (analytics)', async () => {
    const onOpen = vi.fn()
    render(<PdfResultGroups groups={groupPdfHits([hit('a', 2, 1, 'credit')])} query="credit" onOpen={onOpen} />)
    await userEvent.click(screen.getByRole('link', { name: /Open page 2/ }))
    expect(onOpen).toHaveBeenCalled()
  })
})

describe('MarkResults', () => {
  const mark: MarkSearchHit = {
    type: 'highlight',
    annotation_id: 'm1',
    document_id: 'a',
    document_title: 'Taxation module',
    page: 9,
    snippet: 'Section 17(5) blocks credit',
    color: 'g',
    rank: 1,
    link: UNFILED_LINK,
  }
  it('names the colour from the legend and opens at the mark', () => {
    render(<MarkResults hits={[mark]} query="credit" legend={legend} />)
    expect(screen.getByText('Formula')).toBeInTheDocument()
    expect(screen.getByText(/Taxation module · page 9/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Section 17\(5\) blocks/ })).toHaveAttribute(
      'href',
      '/app/notes/pdf/a?page=9&ann=m1',
    )
  })
})

describe('PdfSearchNotices', () => {
  const meta = (rows: Array<{ document_id: string; reason: 'scanned' | 'locked' | 'pending' }>, indexing = 0) => ({
    indexing_documents: indexing,
    not_searchable: rows,
  })
  const titles = new Map([
    ['s', 'Old scan'],
    ['l', 'Locked notes'],
  ])

  it('says documents are still being indexed', () => {
    render(
      <PdfSearchNotices
        indexing="2 documents are still being indexed."
        notSearchable={null}
        titles={titles}
        documents={[]}
        onMakeSearchable={() => undefined}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('2 documents are still being indexed.')
  })

  it('offers Make searchable for a scanned file and Open for a locked one', async () => {
    const rows = meta([
      { document_id: 's', reason: 'scanned' },
      { document_id: 'l', reason: 'locked' },
    ]).not_searchable
    const onMakeSearchable = vi.fn()
    render(
      <PdfSearchNotices
        indexing={null}
        notSearchable={notSearchable(meta(rows))}
        titles={titles}
        documents={rows}
        onMakeSearchable={onMakeSearchable}
      />,
    )
    expect(screen.getByText('2 documents cannot be searched yet (locked or scanned).')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Make searchable: Old scan/ }))
    expect(onMakeSearchable).toHaveBeenCalledWith('s')
    expect(screen.getByRole('link', { name: /Open Locked notes/ })).toHaveAttribute('href', '/app/notes/pdf/l')
  })

  it('renders nothing when there is nothing to say', () => {
    const { container } = render(
      <PdfSearchNotices
        indexing={null}
        notSearchable={null}
        titles={titles}
        documents={[]}
        onMakeSearchable={() => undefined}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('disables the button for the document being opened', () => {
    const rows = [{ document_id: 's', reason: 'scanned' }]
    render(
      <PdfSearchNotices
        indexing={null}
        notSearchable={notSearchable(meta([{ document_id: 's', reason: 'scanned' }]))}
        titles={titles}
        documents={rows}
        onMakeSearchable={() => undefined}
        busyId="s"
      />,
    )
    expect(screen.getByRole('button', { name: /Make searchable/ })).toBeDisabled()
  })
})
