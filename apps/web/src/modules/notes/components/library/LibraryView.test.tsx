import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { DocumentSummary } from '../../lib/document-types'
import { makeDocument } from '../../lib/testing-documents'
import { FALLBACK_UPLOAD_LIMITS, MIB } from '../../lib/upload-check'
import { DocumentCard } from './DocumentCard'
import { LibraryView } from './LibraryView'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const usage = {
  plan: 'free',
  limits: { max_storage_mb: 500, max_documents: 100, max_notes: 1, max_note_chars: 1, max_note_images: 1, max_tags: 1 },
  used: { storage_bytes: 412 * MIB, notes: 0, tags: 0, documents: 7 },
  resets_on: '2026-11-01',
}

const base = {
  state: 'ready' as const,
  items: [],
  filtered: false,
  usage,
  limits: FALLBACK_UPLOAD_LIMITS,
  online: true,
  filters: <div>filters</div>,
  uploads: null,
  hasUploads: false,
  hasMore: false,
  loadingMore: false,
  onLoadMore: () => undefined,
  onRetry: () => undefined,
  onUpload: () => undefined,
  onFiles: () => undefined,
  onClearFilters: () => undefined,
  renderCard: (doc: DocumentSummary) => <DocumentCard doc={doc} />,
}

const docs = (n: number) => Array.from({ length: n }, (_, i) => makeDocument({ id: `d${i}`, title: `Module ${i}` }))

describe('LibraryView states (PRD 7.3)', () => {
  it('first time: an empty library invites the first PDF, with a dropzone and no filters', () => {
    render(<LibraryView {...base} />)
    expect(screen.getByText(/Choose a PDF to upload|Drop a PDF/i)).toBeInTheDocument()
    expect(screen.queryByText('filters')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Upload PDF/ })).toBeEnabled()
  })

  it('loading shows skeletons and announces it', () => {
    render(<LibraryView {...base} state="loading" usage={undefined} />)
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('Loading your PDFs')
    expect(screen.getByText('filters')).toBeInTheDocument()
  })

  it('no match is different from no PDFs and offers to clear the filters', async () => {
    const onClearFilters = vi.fn()
    render(<LibraryView {...base} filtered onClearFilters={onClearFilters} />)
    expect(screen.getByText('No PDFs match')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))
    expect(onClearFilters).toHaveBeenCalled()
  })

  it('error keeps the last list, shows the request id and retries', async () => {
    const onRetry = vi.fn()
    render(<LibraryView {...base} state="error" items={docs(2)} requestId="req-42" onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('This is the last list we had.')
    expect(screen.getByRole('alert')).toHaveTextContent('Request req-42')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('offline says so, and Upload is disabled with its reason', () => {
    render(<LibraryView {...base} online={false} items={docs(1)} />)
    expect(screen.getByText(/Offline: showing the PDFs this device already loaded/)).toBeInTheDocument()
    const upload = screen.getByRole('button', { name: /Upload PDF/ })
    expect(upload).toBeDisabled()
    expect(upload).toHaveAccessibleDescription('You are offline. Upload needs a connection.')
  })

  it('writes the usage out in text', () => {
    render(<LibraryView {...base} items={docs(1)} />)
    expect(screen.getByRole('meter', { name: 'PDF storage' })).toHaveAttribute('aria-valuetext', '412 of 500 MB')
    expect(screen.getByRole('meter', { name: 'PDFs' })).toHaveAttribute('aria-valuetext', '7 of 100')
  })

  it('shows a storage full warning in words', () => {
    render(
      <LibraryView {...base} items={docs(1)} usage={{ ...usage, used: { ...usage.used, storage_bytes: 500 * MIB } }} />,
    )
    expect(screen.getByText('Storage full')).toBeInTheDocument()
  })

  it('pages a long list by cursor and says it is partial', async () => {
    const onLoadMore = vi.fn()
    render(<LibraryView {...base} items={docs(100)} hasMore onLoadMore={onLoadMore} />)
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(100)
    expect(screen.getByText(/Showing 100 PDFs so far/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
    expect(onLoadMore).toHaveBeenCalled()
  })

  it('disables Load more while the next page loads', () => {
    render(<LibraryView {...base} items={docs(3)} hasMore loadingMore />)
    expect(screen.getByRole('button', { name: 'Loading…' })).toBeDisabled()
  })

  it('keeps an upload in progress visible even when the library is empty', () => {
    render(<LibraryView {...base} hasUploads uploads={<p>uploading tax.pdf</p>} />)
    expect(screen.getByText('uploading tax.pdf')).toBeInTheDocument()
    expect(screen.queryByText(/Drop a PDF/)).not.toBeInTheDocument()
  })
})

describe('DocumentCard states', () => {
  const title =
    'A very long module title that goes on and on about indirect taxation, input tax credit and everything else a student could ever want in one PDF'
  it('wraps a long title inside the card and links to the reader', () => {
    render(<DocumentCard doc={makeDocument({ title })} />)
    const link = screen.getByRole('link', { name: title })
    expect(link).toHaveAttribute('href', '/app/notes/pdf/dddddddd-dddd-4ddd-8ddd-dddddddddddd')
    expect(link.className + (link.parentElement?.className ?? '')).toMatch(/break-words|line-clamp/)
  })

  it('partial: a preparing file and a file in OCR show words, not only colour', () => {
    const { rerender } = render(<DocumentCard doc={makeDocument({ status: 'scanning', page_count: null })} />)
    expect(screen.getByText('Preparing')).toBeInTheDocument()
    rerender(
      <DocumentCard
        doc={makeDocument({ is_scanned: true, ocr_status: 'running', ocr_pages_done: 120, ocr_pages_total: 320 })}
      />,
    )
    expect(screen.getByText('OCR 120 of 320')).toBeInTheDocument()
  })

  it('a scanned file without OCR offers Make searchable', async () => {
    const onMakeSearchable = vi.fn()
    const doc = makeDocument({ is_scanned: true, ocr_status: 'none' })
    render(<DocumentCard doc={doc} onMakeSearchable={onMakeSearchable} />)
    expect(screen.getByText('Scanned, search off')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Make searchable/ }))
    expect(onMakeSearchable).toHaveBeenCalledWith(doc)
  })

  it('a locked file still opens, and a rejected one does not', () => {
    const { rerender } = render(<DocumentCard doc={makeDocument({ status: 'needs_password' })} />)
    expect(screen.getByText('Locked')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Taxation module/ })).toBeInTheDocument()
    rerender(<DocumentCard doc={makeDocument({ status: 'rejected' })} />)
    expect(screen.getByText('Rejected')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Taxation module/ })).not.toBeInTheDocument()
  })

  it('resume adds a Continue link to the last page', () => {
    render(<DocumentCard doc={makeDocument({ last_page: 14, last_opened_at: '2026-10-01T00:00:00Z' })} resume />)
    expect(screen.getByRole('link', { name: /Continue on page 14/ })).toHaveAttribute(
      'href',
      expect.stringContaining('page=14'),
    )
  })

  it('its menu is a 44 px target and runs the actions', async () => {
    const onEdit = vi.fn()
    const onTrash = vi.fn()
    const doc = makeDocument()
    render(<DocumentCard doc={doc} onEdit={onEdit} onTrash={onTrash} />)
    const menu = screen.getByRole('button', { name: /More actions|Actions|Menu/i })
    expect(menu.className).toMatch(/size-11|min-h-11/)
    await userEvent.click(menu)
    await userEvent.click(within(screen.getByRole('menu')).getByRole('menuitem', { name: /Edit|Details/ }))
    expect(onEdit).toHaveBeenCalledWith(doc)
  })

  it('compact has no menu', () => {
    render(<DocumentCard doc={makeDocument()} compact onEdit={() => undefined} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
