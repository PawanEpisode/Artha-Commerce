import 'fake-indexeddb/auto'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { UNFILED_LINK } from '../lib/testing'
import { makeDocument } from '../lib/testing-documents'
import { NotesSearchContainer } from './NotesSearchContainer'

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  pdfOn: { value: true },
  track: vi.fn(),
}))

vi.mock('~/lib/api', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  api: mocks.api,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('@tanstack/react-router', async () => {
  const stub = (await import('~/test/router-stub')).routerStub
  return { ...stub, useNavigate: () => vi.fn() }
})
vi.mock('~/modules/observability', () => ({
  useFeatureFlag: () => mocks.pdfOn.value,
  track: (...args: unknown[]) => mocks.track(...args),
  ageBucket: () => '<1h',
}))
vi.mock('~/modules/coverage', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useOverview: () => ({ data: undefined, isPending: false, isError: false, refetch: () => undefined }),
}))
vi.mock('./NotesShell', () => ({ NotesShell: ({ children }: { children: ReactNode }) => <>{children}</> }))

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
)

const legend = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }
const pdfHit = (page: number, snippet: string) => ({
  type: 'pdf',
  document_id: 'doc-1',
  document_title: 'Taxation module',
  page,
  snippet,
  rank: page,
  link: UNFILED_LINK,
})

function respond(search: object) {
  mocks.api.mockImplementation(async (path: string) => {
    if (path.startsWith('/notes/search/')) return search
    if (path.startsWith('/notes/usage/'))
      return {
        plan: 'free',
        limits: { max_storage_mb: 500, max_documents: 100, ocr_pages_per_month: 500, exports_per_month: 10 },
        used: { storage_bytes: 0, documents: 1, ocr_pages: 0, exports: 0, notes: 0, tags: 0 },
        resets_on: '2026-11-01',
      }
    if (path.startsWith('/notes/settings/'))
      return {
        color_legend: legend,
        default_color: 'y',
        page_tone: 'original',
        finger_draws: false,
        ocr_default: 'ask',
        ocr_lang: 'eng',
        legend_schema: 1,
      }
    if (path.startsWith('/notes/documents/') && path.includes('doc-1'))
      return makeDocument({ id: 'doc-1', is_scanned: true, ocr_status: 'none' })
    if (path.startsWith('/notes/documents/'))
      return { items: [{ ...makeDocument({ id: 's1', title: 'Old scan' }) }], next_cursor: null }
    return {}
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.pdfOn.value = true
  localStorage.clear()
})

describe('PDF search', () => {
  it('searches PDFs, groups pages by document with marked words, and opens a page', async () => {
    respond({
      items: [pdfHit(14, 'input tax credit is blocked'), pdfHit(20, 'credit notes')],
      next_cursor: null,
      meta: { indexing_documents: 0, not_searchable: [] },
    })
    render(<NotesSearchContainer search={{ q: 'credit', scope: 'pdf' }} />, { wrapper })
    const group = (await screen.findByRole('heading', { name: 'Taxation module' })).closest('li') as HTMLElement
    expect(within(group).getByRole('link', { name: /Open page 14 of Taxation module/ })).toHaveAttribute(
      'href',
      '/app/notes/pdf/doc-1?page=14&q=credit',
    )
    expect(within(group).getAllByText('credit')[0]?.tagName).toBe('MARK')
    expect(mocks.api).toHaveBeenCalledWith(expect.stringContaining('scope=pdf'))
    await waitFor(() =>
      expect(mocks.track).toHaveBeenCalledWith('notes_search_performed', expect.objectContaining({ scope: 'pdf' })),
    )
    await userEvent.click(within(group).getByRole('link', { name: /Open page 14/ }))
    expect(mocks.track).toHaveBeenCalledWith('search_result_opened', expect.objectContaining({ scope: 'pdf' }))
    const sent = JSON.stringify(mocks.track.mock.calls)
    expect(sent).not.toContain('credit')
  })

  it('shows the PDFs scope only when the flag is on', async () => {
    respond({ items: [], next_cursor: null })
    const { unmount } = render(<NotesSearchContainer search={{}} />, { wrapper })
    expect(screen.getByRole('radio', { name: 'PDFs' })).toBeInTheDocument()
    unmount()
    mocks.pdfOn.value = false
    render(<NotesSearchContainer search={{ scope: 'pdf' }} />, { wrapper })
    expect(screen.queryByRole('radio', { name: 'PDFs' })).not.toBeInTheDocument()
  })

  it('says documents are still being indexed and offers Make searchable for a scanned one', async () => {
    respond({
      items: [pdfHit(2, 'credit')],
      next_cursor: null,
      meta: { indexing_documents: 2, not_searchable: [{ document_id: 'doc-1', reason: 'scanned' }] },
    })
    render(<NotesSearchContainer search={{ q: 'credit', scope: 'all' }} />, { wrapper })
    expect(await screen.findByText(/2 documents are still being indexed/)).toBeInTheDocument()
    expect(screen.getByText('1 document cannot be searched yet (scanned).')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Make searchable: / }))
    expect(await screen.findByRole('dialog')).toHaveTextContent('Make this PDF searchable')
  })

  it('names the empty PDF result in words', async () => {
    respond({ items: [], next_cursor: null, meta: { indexing_documents: 0, not_searchable: [] } })
    render(<NotesSearchContainer search={{ q: 'zzz', scope: 'pdf' }} />, { wrapper })
    expect(await screen.findByText('No PDF pages match')).toBeInTheDocument()
  })

  it('shows mark hits with the legend name of the colour', async () => {
    respond({
      items: [
        {
          type: 'highlight',
          annotation_id: 'm1',
          document_id: 'doc-1',
          document_title: 'Taxation module',
          page: 9,
          snippet: 'credit is blocked',
          color: 'g',
          rank: 1,
          link: UNFILED_LINK,
        },
      ],
      next_cursor: null,
    })
    render(<NotesSearchContainer search={{ q: 'credit' }} />, { wrapper })
    expect(await screen.findByText('Formula')).toBeInTheDocument()
  })
})
