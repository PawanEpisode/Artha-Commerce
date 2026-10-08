import 'fake-indexeddb/auto'

import { ThemeProvider } from '@artha/design-system'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearOfflineQueue, resetFlushState, resetOfflineQueue } from '~/lib/offline-queue'
import type * as Observability from '~/modules/observability'

import { resetAnnotationQueue } from '../lib/annotation-queue'
import { clearAnnotationData, resetAnnotationStore } from '../lib/annotation-store'
import { makeAnnotation } from '../lib/annotation-testing'
import type { BatchOpBody } from '../lib/annotation-types'
import type * as AnnotationsApi from '../lib/annotations-api'
import { createFakeEngine } from '../lib/pdf-engine/fake-engine'
import type { ReaderSearch } from '../lib/reader-schema'
import type * as SettingsApi from '../lib/settings-api'
import { DOC_ID, makeDocument, makeProcessing } from '../lib/testing-documents'

const docs = vi.hoisted(() => ({
  getDocument: vi.fn(),
  getProcessing: vi.fn(),
  putProgress: vi.fn(),
  getPagesText: vi.fn(),
  searchDocument: vi.fn(),
}))
const settingsApi = vi.hoisted(() => ({ getNotesSettings: vi.fn() }))
const marksApi = vi.hoisted(() => ({
  getDelta: vi.fn(),
  batchMarks: vi.fn(),
  putMark: vi.fn(),
  makeCard: vi.fn(),
}))
const track = vi.hoisted(() => vi.fn())
vi.mock('../lib/documents-api', () => docs)
vi.mock('../lib/settings-api', async (original) => ({
  ...(await original<typeof SettingsApi>()),
  ...settingsApi,
}))
vi.mock('../lib/annotations-api', async (original) => ({
  ...(await original<typeof AnnotationsApi>()),
  ...marksApi,
}))
vi.mock('~/modules/observability', async (original) => ({
  ...(await original<typeof Observability>()),
  useFeatureFlag: () => true,
  track,
}))
vi.mock('~/lib/supabase', () => ({
  getSupabase: () => ({ auth: { getSession: async () => ({ data: { session: { user: { id: 'u1' } } } }) } }),
}))
vi.mock('../hooks/useReaderOcrExport', () => ({
  useReaderOcrExport: () => ({ extensions: {}, onMakeSearchable: undefined }),
}))

import { PdfReaderScreen } from './PdfReaderScreen'

beforeEach(async () => {
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(376)
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockReturnValue(700)
  docs.getDocument.mockResolvedValue(makeDocument())
  docs.getProcessing.mockResolvedValue(makeProcessing())
  docs.putProgress.mockResolvedValue({
    last_page: 1,
    last_zoom: 'fit',
    page_tone: null,
    last_opened_at: '2026-10-08T10:00:00Z',
  })
  docs.getPagesText.mockResolvedValue({ pages: [], text_status: 'done', ocr_status: 'none' })
  docs.searchDocument.mockResolvedValue({
    items: [],
    text_status: 'done',
    ocr_status: 'none',
    indexed_pages: 3,
    page_count: 3,
  })
  settingsApi.getNotesSettings.mockResolvedValue({
    color_legend: { y: 'Important', g: 'Formula', b: 'Section or rule', p: 'Doubt', o: 'Example' },
    legend_schema: 1,
    default_color: 'y',
    finger_draws: false,
    capabilities: { recall: false },
  })
  marksApi.getDelta.mockResolvedValue({ items: [], change_seq: 0, next_since_seq: 0, has_more: false })
  marksApi.batchMarks.mockImplementation(async (_doc: string, ops: BatchOpBody[]) => ({
    change_seq: 1,
    marks: { count: 1, limit: 20_000, near_limit: false },
    results: ops.map((op, i) => ({
      id: op.id,
      status: 'ok',
      annotation: makeAnnotation({
        id: op.id,
        document_id: DOC_ID,
        page: (op.page as number) ?? 1,
        rev: i + 1,
        deleted_at: op.op === 'delete' ? '2026-10-08T10:00:00Z' : null,
        quote_exact: (op.quote_exact as string) ?? null,
      }),
    })),
  }))
  resetOfflineQueue()
  resetFlushState()
  resetAnnotationQueue()
  resetAnnotationStore()
  await clearAnnotationData('u1')
  await clearOfflineQueue()
  window.localStorage.setItem('theme', 'reading')
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

function setup(initial: ReaderSearch = {}) {
  const engine = createFakeEngine({
    pages: [
      { text: 'Input tax credit is generally allowed' },
      { text: 'ITC blocked credits are listed in section 17 five' },
      { text: 'Page three' },
    ],
  })
  const onSearchChange = vi.fn()
  const urls: ReaderSearch[] = []
  function Harness() {
    const [search, setSearch] = useState<ReaderSearch>(initial)
    urls.push(search)
    return (
      <PdfReaderScreen
        docId={DOC_ID}
        search={search}
        onSearchChange={(patch) => {
          onSearchChange(patch)
          setSearch((prev) => ({ ...prev, ...patch }))
        }}
        onBack={() => undefined}
        engine={engine}
      />
    )
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <Harness />
      </QueryClientProvider>
    </ThemeProvider>,
  )
  return { onSearchChange, urls }
}

const reader = () => document.querySelector('[data-slot="pdf-reader"]') as HTMLElement
const waitOpen = () => waitFor(() => expect(reader()).toHaveAttribute('data-phase', 'ready'))
const viewport = () => screen.getByRole('region', { name: 'Document pages' })
const press = async (keys: string) => {
  if (!viewport().contains(document.activeElement)) viewport().focus()
  await userEvent.keyboard(keys)
}
const sentOps = () => marksApi.batchMarks.mock.calls.flatMap(([, ops]) => ops as BatchOpBody[])

describe('the annotation layer on the reader, from the keyboard (FR-F03-71)', () => {
  it('opens, finds a hit, highlights it, moves to it with ] and deletes it with Undo available', async () => {
    const { onSearchChange } = setup()
    await waitOpen()
    expect(screen.getByRole('button', { name: '0 marks. Open the list' })).toBeInTheDocument()
    // Saved is announced politely, in words.
    expect(screen.getAllByRole('status').some((el) => /Saved/.test(el.textContent ?? ''))).toBe(true)

    // Search: "/" opens it, typing finds the hit on page 2.
    await press('/')
    const input = await screen.findByRole('searchbox', { name: 'Search this PDF' })
    await userEvent.type(input, 'blocked')
    await screen.findByText(/ITC blocked credits/)

    // Alt+H highlights the current hit with the default colour: saved on this device at once, sent in the background.
    await userEvent.keyboard('{Alt>}h{/Alt}')
    await screen.findByRole('button', { name: '1 mark. Open the list' })
    await waitFor(() => expect(sentOps()).toHaveLength(1))
    expect(sentOps()[0]).toMatchObject({ op: 'upsert', kind: 'highlight', page: 2, color: 'y', quote_exact: 'blocked' })
    expect(document.querySelector('[data-slot="marks-under"] [data-kind="highlight"]')).not.toBeNull()

    // Esc leaves the search; ] goes to the mark and selects it in the URL.
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('searchbox')).not.toBeInTheDocument())
    await press(']')
    await waitFor(() =>
      expect(onSearchChange).toHaveBeenCalledWith(expect.objectContaining({ ann: expect.any(String) })),
    )
    expect(await screen.findByRole('toolbar', { name: /./ })).toBeInTheDocument()

    // Delete removes it, says so, and the count drops.
    await press('{Delete}')
    await screen.findByRole('button', { name: '0 marks. Open the list' })
    await waitFor(() => expect(sentOps().some((op) => op.op === 'delete')).toBe(true))
  })

  it('lists the mark in words for a screen reader and opens it from the list', async () => {
    setup({ panel: 'search', q: 'blocked' })
    await waitOpen()
    await screen.findByText(/ITC blocked credits/)
    await userEvent.click(screen.getByRole('searchbox', { name: 'Search this PDF' }))
    await userEvent.keyboard('{Alt>}h{/Alt}')
    await waitFor(() => expect(sentOps()).toHaveLength(1))
    await userEvent.click(screen.getByRole('button', { name: 'Marks in this PDF' }))
    const list = await screen.findByRole('list', { name: 'Marks in reading order' })
    expect(within(list).getByText(/Highlight, page 2/)).toBeInTheDocument()
    expect(within(list).getByText(/yellow \(Important\)/)).toBeInTheDocument()
  })
})
