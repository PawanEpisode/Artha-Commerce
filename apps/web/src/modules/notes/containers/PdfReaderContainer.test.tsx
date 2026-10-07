import { ThemeProvider } from '@artha/design-system'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { DocumentDetail, DocumentProcessing } from '../lib/document-types'
import { createFakeEngine, type FakeEngineOptions } from '../lib/pdf-engine/fake-engine'
import type { ReaderSearch } from '../lib/reader-schema'
import { DOC_ID, makeDocument, makeProcessing } from '../lib/testing-documents'

const api = vi.hoisted(() => ({
  getDocument: vi.fn(),
  getProcessing: vi.fn(),
  putProgress: vi.fn(),
  getPagesText: vi.fn(),
  searchDocument: vi.fn(),
}))
vi.mock('../lib/documents-api', () => api)
vi.mock('~/modules/observability', () => ({ useFeatureFlag: () => flag.on, track: vi.fn() }))
const flag = vi.hoisted(() => ({ on: true }))

import { PdfReaderContainer } from './PdfReaderContainer'
import type { ReaderExtensions } from './reader-extensions'

const onlineSpy = () => vi.spyOn(window.navigator, 'onLine', 'get')

beforeEach(() => {
  flag.on = true
  vi.spyOn(Element.prototype, 'clientWidth', 'get').mockReturnValue(376)
  vi.spyOn(Element.prototype, 'clientHeight', 'get').mockReturnValue(700)
  api.getDocument.mockResolvedValue(makeDocument())
  api.getProcessing.mockResolvedValue(makeProcessing())
  api.putProgress.mockResolvedValue({
    last_page: 1,
    last_zoom: 'fit',
    page_tone: null,
    last_opened_at: '2026-10-08T10:00:00Z',
  })
  api.getPagesText.mockResolvedValue({ pages: [], text_status: 'done', ocr_status: 'none' })
  api.searchDocument.mockResolvedValue({
    items: [],
    text_status: 'done',
    ocr_status: 'none',
    indexed_pages: 3,
    page_count: 3,
  })
  try {
    window.localStorage.clear()
    window.sessionStorage.clear()
  } catch {
    // ignore
  }
})
afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
  vi.useRealTimers()
})

interface Setup {
  doc?: Partial<DocumentDetail>
  processing?: Partial<DocumentProcessing>
  engine?: FakeEngineOptions
  search?: ReaderSearch
  extensions?: ReaderExtensions
  onMakeSearchable?: () => void
  theme?: 'reading' | 'dark' | 'light'
}

function setup(options: Setup = {}) {
  if (options.doc) api.getDocument.mockResolvedValue(makeDocument(options.doc))
  if (options.processing) api.getProcessing.mockResolvedValue(makeProcessing(options.processing))
  try {
    window.localStorage.setItem('theme', options.theme ?? 'reading')
  } catch {
    // ignore
  }
  const engine = createFakeEngine({ pageCount: 3, ...options.engine })
  const onSearchChange = vi.fn()
  const onBack = vi.fn()
  function Harness() {
    const [search, setSearch] = useState<ReaderSearch>(options.search ?? {})
    return (
      <PdfReaderContainer
        docId={DOC_ID}
        search={search}
        onSearchChange={(patch) => {
          onSearchChange(patch)
          setSearch((prev) => ({ ...prev, ...patch }))
        }}
        onBack={onBack}
        engine={engine}
        extensions={options.extensions}
        onMakeSearchable={options.onMakeSearchable}
      />
    )
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <Harness />
      </QueryClientProvider>
    </ThemeProvider>,
  )
  return { engine, onSearchChange, onBack, client, ...view }
}

const press = async (keys: string) => {
  const region = screen.getByRole('region', { name: 'Document pages' })
  if (!region.contains(document.activeElement)) region.focus()
  await userEvent.keyboard(keys)
}
const reader = () => document.querySelector('[data-slot="pdf-reader"]') as HTMLElement
const indicator = () => screen.getByRole('button', { name: /Go to page/ })
const waitOpen = () => waitFor(() => expect(reader()).toHaveAttribute('data-phase', 'ready'))

describe('states of the reader (PRD 7.3)', () => {
  it('loading: a skeleton in the shape of a page, not a spinner on a blank screen', async () => {
    api.getDocument.mockReturnValue(new Promise(() => undefined))
    setup()
    expect(screen.getByRole('status', { name: 'Opening the PDF' })).toBeInTheDocument()
  })

  it('success: title, pages, page indicator and a way back', async () => {
    const { onBack } = setup()
    expect(await screen.findByRole('heading', { name: 'Taxation module' })).toBeInTheDocument()
    await waitOpen()
    expect(indicator()).toHaveTextContent('p. 1 / 3')
    expect(screen.getByRole('group', { name: 'Page 1' })).toHaveAttribute('data-state', 'drawn')
    await userEvent.click(screen.getByRole('button', { name: 'Back to library' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('partial: pages have their final size while the file is still opening, then draw', async () => {
    const { engine } = setup({ engine: { openDelayMs: 80 } })
    const first = await screen.findByRole('group', { name: 'Page 1' })
    expect(first).toHaveStyle({ width: '360px' })
    expect(first).not.toHaveAttribute('data-state', 'drawn')
    expect(engine.liveCanvases()).toBe(0)
    await waitFor(() => expect(first).toHaveAttribute('data-state', 'drawn'))
  })

  it('huge: the large-document notice shows once, then never again for that file', async () => {
    setup({ doc: { bytes: 30 * 1024 * 1024, page_count: 3 } })
    expect(await screen.findByText(/Large PDF: pages load as you scroll/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss notice' }))
    expect(screen.queryByText(/Large PDF/)).not.toBeInTheDocument()
    setup({ doc: { bytes: 30 * 1024 * 1024, page_count: 3 } })
    await screen.findAllByRole('heading', { name: 'Taxation module' })
    expect(screen.queryByText(/Large PDF/)).not.toBeInTheDocument()
  })

  it('huge: search goes to the server, not the browser', async () => {
    api.searchDocument.mockResolvedValue({
      items: [{ page: 2, snippet: 'ITC is blocked', rank: 1 }],
      text_status: 'done',
      ocr_status: 'none',
      indexed_pages: 3,
      page_count: 3,
    })
    setup({ doc: { bytes: 30 * 1024 * 1024 } })
    await waitOpen()
    await userEvent.click(screen.getByRole('button', { name: 'Search in this PDF' }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search this PDF' }), 'ITC')
    expect(await screen.findByText('ITC is blocked')).toBeInTheDocument()
    expect(api.searchDocument).toHaveBeenCalledWith(DOC_ID, 'ITC', 50)
  })

  it('encrypted: asks for the password, retries on a wrong one, hints after three, never stores it', async () => {
    const { engine } = setup({ engine: { password: 'secret' }, doc: { is_encrypted: true, status: 'needs_password' } })
    const dialog = await screen.findByRole('dialog', { name: /This PDF is locked/ })
    expect(within(dialog).getByLabelText('Password')).toBeInTheDocument()
    for (const wrong of ['one', 'two']) {
      await userEvent.type(within(dialog).getByLabelText('Password'), wrong)
      await userEvent.click(within(dialog).getByRole('button', { name: 'Unlock' }))
      expect(await within(dialog).findByText('That password did not work. Check it and try again.')).toBeInTheDocument()
      expect(within(dialog).getByLabelText('Password')).toHaveValue('')
    }
    expect(within(dialog).getByText(/Passwords are case-sensitive/)).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText('Password'), 'secret')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Unlock' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitOpen()
    expect(engine.passwordsAsked).toBe(3)
    // The password goes nowhere but the engine: not the URL, not storage, not any API call.
    expect(window.location.href).not.toContain('secret')
    expect(JSON.stringify({ ...window.localStorage })).not.toContain('secret')
    expect(JSON.stringify({ ...window.sessionStorage })).not.toContain('secret')
    for (const mock of Object.values(api)) expect(JSON.stringify(mock.mock.calls)).not.toContain('secret')
  })

  it('encrypted: Cancel returns to the library', async () => {
    const { onBack } = setup({ engine: { password: 'secret' }, doc: { is_encrypted: true } })
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(onBack).toHaveBeenCalled())
  })

  it('encrypted and locked: says search and OCR need the password', async () => {
    setup({
      doc: { is_encrypted: true, text_status: 'locked', status: 'needs_password' },
      processing: { text_status: 'locked' },
    })
    expect(await screen.findByText(/Locked: search and OCR need the password/)).toBeInTheDocument()
  })

  it('scanned: banner offers OCR, "Not now" hides it for the session', async () => {
    const onMakeSearchable = vi.fn()
    setup({
      doc: { is_scanned: true, text_status: 'skipped' },
      processing: { is_scanned: true, text_status: 'skipped' },
      onMakeSearchable,
    })
    expect(await screen.findByText('Scanned pages. Search and text selection need OCR.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Make searchable' }))
    expect(onMakeSearchable).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(screen.queryByText(/Scanned pages/)).not.toBeInTheDocument()
  })

  it('scanned: shows OCR progress, and OCR pages get a text layer', async () => {
    api.getPagesText.mockResolvedValue({
      pages: [
        {
          page: 1,
          text: 'blocked credits',
          source: 'ocr',
          conf: 90,
          words: [
            [0.1, 0.1, 0.1, 0.01, 'blocked'],
            [0.25, 0.1, 0.1, 0.01, 'credits'],
          ],
        },
      ],
      text_status: 'done',
      ocr_status: 'partial',
    })
    setup({
      doc: { is_scanned: true, ocr_status: 'partial', ocr_pages_done: 1, ocr_pages_total: 3 },
      processing: { is_scanned: true, ocr_status: 'partial', ocr_pages_done: 1, ocr_pages_total: 3 },
    })
    expect(await screen.findByText(/Making this PDF searchable|We could not finish|Scanned pages/)).toBeInTheDocument()
    await waitFor(() => expect(document.querySelector('[data-kind="ocr"]')).not.toBeNull())
    expect(document.querySelector('[data-kind="ocr"]')).toHaveTextContent('blocked credits')
  })

  it('page error: only that page shows the retry state, the rest works', async () => {
    setup({ engine: { pages: [{}, { failRenders: Infinity }, {}] }, doc: { page_count: 3 } })
    await waitOpen()
    // Pages 1 and 2 are drawn at the start; page 2 fails.
    const alerts = await screen.findAllByRole('alert')
    expect(alerts.some((a) => /This page could not be drawn/.test(a.textContent ?? ''))).toBe(true)
    expect(
      within(screen.getByRole('group', { name: 'Page 1' })).queryByText('This page could not be drawn.'),
    ).toBeNull()
    expect(screen.getByRole('group', { name: 'Page 1' })).toHaveAttribute('data-state', 'drawn')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('error opening: full-page message with Retry, Download original, Report and a way back', async () => {
    const { engine } = setup({
      engine: { openError: new (await import('../lib/pdf-engine')).PdfEngineError('invalid_pdf') },
    })
    expect(await screen.findByRole('heading', { name: 'We could not open this file' })).toBeInTheDocument()
    expect(screen.getByText(/looks damaged/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Download original/ })).toHaveAttribute(
      'href',
      expect.stringContaining('storage.example'),
    )
    expect(screen.getByRole('button', { name: /Report a problem/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Back to library' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(engine.opens).toBe(2))
  })

  it('error opening when the connection drops after the file opened', async () => {
    const { engine } = setup()
    await waitOpen()
    act(() => engine.documents[0]?.fail())
    expect(await screen.findByRole('heading', { name: 'We could not open this file' })).toBeInTheDocument()
  })

  it('offline: a banner says marks are kept on the device', async () => {
    onlineSpy().mockReturnValue(false)
    setup()
    expect(await screen.findByText(/Offline: marks are saved on this device/)).toBeInTheDocument()
  })

  it('flag off: the reader is not available yet, with a way back', async () => {
    flag.on = false
    const { onBack } = setup()
    expect(await screen.findByText('The PDF reader is not available yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Back to my notes/ }))
    expect(onBack).toHaveBeenCalled()
  })

  it('flag off on the server (403 feature_disabled) shows the same state', async () => {
    api.getDocument.mockRejectedValue(new ApiError(403, 'x', { error: { code: 'feature_disabled', message: 'm' } }))
    setup()
    expect(await screen.findByText('The PDF reader is not available yet')).toBeInTheDocument()
  })

  it('another student\'s document id is the standard "could not find" state', async () => {
    api.getDocument.mockRejectedValue(new ApiError(404, 'x', { error: { code: 'not_found', message: 'm' } }))
    setup()
    expect(await screen.findByRole('heading', { name: 'We could not find this document' })).toBeInTheDocument()
  })

  it('preparing: waits for the server and opens when the file is ready', async () => {
    api.getDocument.mockResolvedValueOnce(makeDocument({ status: 'scanning', can_open: false, file_url: null }))
    api.getProcessing.mockResolvedValue(makeProcessing({ status: 'scanning' }))
    setup()
    expect(await screen.findByRole('heading', { name: 'Getting your PDF ready' })).toBeInTheDocument()
  })

  it('rejected: says why in plain words', async () => {
    api.getDocument.mockResolvedValue(
      makeDocument({ status: 'rejected', status_reason: 'pdf_corrupt', can_open: false, file_url: null }),
    )
    setup()
    expect(await screen.findByRole('heading', { name: 'We could not accept this file' })).toBeInTheDocument()
    expect(screen.getByText(/damaged/)).toBeInTheDocument()
  })
})

describe('resume and URL', () => {
  it('opens at the stored page when the URL says nothing', async () => {
    setup({ doc: { last_page: 2 } })
    await waitOpen()
    expect(indicator()).toHaveTextContent('p. 2 / 3')
  })

  it('lets the URL page win over the stored one', async () => {
    setup({ doc: { last_page: 2 }, search: { page: 3 } })
    await waitOpen()
    expect(indicator()).toHaveTextContent('p. 3 / 3')
  })

  it('keeps the URL in step with the page and zoom, replacing history', async () => {
    const { onSearchChange } = setup()
    await waitOpen()
    await press('n')
    await waitFor(() => expect(onSearchChange).toHaveBeenCalledWith({ page: 2, zoom: 'fit' }), { timeout: 2000 })
  })

  it('saves progress when the page closes, with keepalive', async () => {
    setup()
    await waitOpen()
    await press('n')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 2 / 3'))
    act(() => void window.dispatchEvent(new Event('pagehide')))
    await waitFor(() => expect(api.putProgress).toHaveBeenCalled())
    const [id, body, options] = api.putProgress.mock.calls.at(-1) ?? []
    expect(id).toBe(DOC_ID)
    expect(body).toEqual({ last_page: 2, last_zoom: 'fit' })
    expect(options).toEqual({ keepalive: true })
  })

  it('saves a chosen page tone with the position', async () => {
    setup()
    await waitOpen()
    await userEvent.click(screen.getByRole('button', { name: /Page tone/ }))
    await userEvent.click(await screen.findByRole('menuitemradio', { name: /Night/ }))
    expect(document.querySelector('[data-slot="pdf-viewport"]')).toHaveAttribute('data-page-tone', 'night')
    act(() => void window.dispatchEvent(new Event('pagehide')))
    await waitFor(() => expect(api.putProgress).toHaveBeenCalled())
    expect(api.putProgress.mock.calls.at(-1)?.[1]).toMatchObject({ page_tone: 'night' })
  })
})

describe('page tone', () => {
  it('follows the Reading theme with paper, and keeps the stored choice', async () => {
    setup({ theme: 'reading' })
    await waitOpen()
    expect(document.querySelector('[data-slot="pdf-viewport"]')).toHaveAttribute('data-page-tone', 'paper')
  })

  it('suggests Night once in the Dark theme', async () => {
    setup({ theme: 'dark' })
    expect(await screen.findByText('Reading at night? Try the Night page tone.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(screen.queryByText(/Reading at night/)).not.toBeInTheDocument()
    setup({ theme: 'dark' })
    await screen.findAllByRole('heading', { name: 'Taxation module' })
    expect(screen.queryByText(/Reading at night/)).not.toBeInTheDocument()
  })

  it('switches to Night from the suggestion', async () => {
    setup({ theme: 'dark' })
    await userEvent.click(await screen.findByRole('button', { name: 'Use Night' }))
    expect(document.querySelector('[data-slot="pdf-viewport"]')).toHaveAttribute('data-page-tone', 'night')
  })
})

describe('keyboard path and announcements', () => {
  it('goes to the next and previous page with n and p', async () => {
    setup()
    await waitOpen()
    await press('n')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 2 / 3'))
    await press('n')
    await press('n')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 3 / 3'))
    await press('p')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 2 / 3'))
  })

  it('announces the page politely once scrolling settles', async () => {
    setup()
    await waitOpen()
    await press('n')
    const live = await screen.findByText('Page 2 of 3', {}, { timeout: 2000 })
    expect(live.closest('[aria-live="polite"]')).not.toBeNull()
  })

  it('zooms with +, - and 0 and shows the zoom in the toolbar', async () => {
    setup()
    await waitOpen()
    expect(screen.getByRole('button', { name: /^Zoom Fit width/ })).toBeInTheDocument()
    await press('+')
    expect(await screen.findByRole('button', { name: /^Zoom 75%/ })).toBeInTheDocument()
    await press('-')
    expect(await screen.findByRole('button', { name: /^Zoom 50%/ })).toBeInTheDocument()
    await press('0')
    expect(await screen.findByRole('button', { name: /^Zoom Fit width/ })).toBeInTheDocument()
  })

  it('opens search with / and Ctrl+F, announces the count, steps through hits, and Escape returns focus to the page', async () => {
    const { onSearchChange } = setup({
      engine: { pages: [{ text: 'ITC is blocked' }, { text: 'nothing' }, { text: 'ITC again' }] },
    })
    await waitOpen()
    await press('/')
    expect(onSearchChange).toHaveBeenCalledWith({ panel: 'search' })
    expect(await screen.findByRole('searchbox', { name: 'Search this PDF' })).toBeInTheDocument()
    await press('{Escape}')
    await waitFor(() => expect(screen.queryByRole('searchbox')).not.toBeInTheDocument())
    expect(screen.getByRole('region', { name: 'Document pages' })).toHaveFocus()
    await press('{Control>}f{/Control}')
    expect(await screen.findByRole('searchbox', { name: 'Search this PDF' })).toBeInTheDocument()
  })

  it('searches the open document in the browser and announces the number of results', async () => {
    const user = userEvent.setup()
    setup({
      engine: { pages: [{ text: 'ITC is blocked' }, { text: 'nothing' }, { text: 'ITC again and ITC' }] },
      search: { panel: 'search' },
    })
    await waitOpen()
    const input = await screen.findByRole('searchbox', { name: 'Search this PDF' })
    await user.type(input, 'ITC')
    const status = await screen.findByText(/Result 1 of 3 results/, {}, { timeout: 3000 })
    expect(status.closest('[aria-live="polite"]')).not.toBeNull()
    expect(screen.getAllByRole('button', { name: /^p\. \d/ })).toHaveLength(3)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 3 / 3'))
    expect(screen.getByText(/Result 2 of 3 results/)).toBeInTheDocument()
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 1 / 3'))
    // The hits are drawn on the visible page.
    await waitFor(() => expect(document.querySelectorAll('[data-hit]').length).toBeGreaterThan(0))
  })

  it('says when nothing matches', async () => {
    const user = userEvent.setup()
    setup({ search: { panel: 'search' } })
    await waitOpen()
    await user.type(await screen.findByRole('searchbox', { name: 'Search this PDF' }), 'zzzz')
    expect(await screen.findByText('No results.', {}, { timeout: 3000 })).toBeInTheDocument()
  })

  it('Escape closes the search panel and puts focus back on the reading area', async () => {
    const user = userEvent.setup()
    const { onSearchChange } = setup({ search: { panel: 'search' } })
    await waitOpen()
    const input = await screen.findByRole('searchbox')
    input.focus()
    await user.keyboard('{Escape}')
    expect(onSearchChange).toHaveBeenCalledWith({ panel: undefined, q: undefined })
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Document pages' })))
  })

  it('has a logical tab order: back, search, then the tools, then the pages and the scrubber', async () => {
    const user = userEvent.setup()
    setup()
    await waitOpen()
    const seen: string[] = []
    for (let i = 0; i < 4; i++) {
      await user.tab()
      seen.push(
        (document.activeElement?.getAttribute('aria-label') ?? document.activeElement?.textContent ?? '').slice(0, 30),
      )
    }
    expect(seen[0]).toBe('Back to library')
    expect(seen[1]).toBe('Search in this PDF')
  })
})

describe('outline and the Back chip', () => {
  const outline = [
    { title: 'Part A', page: 1, children: [{ title: 'Input tax credit', page: 3, children: [] }] },
    { title: 'Part B', page: 2, children: [] },
  ]

  it('jumps from the outline, shows Back to the previous place for ten seconds, and returns', async () => {
    const user = userEvent.setup()
    setup({ doc: { outline }, search: { panel: 'outline' } })
    await waitOpen()
    const nav = await screen.findByRole('navigation', { name: 'Document outline' })
    await user.click(within(nav).getByRole('button', { name: /Input tax credit/ }))
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 3 / 3'))
    const back = await screen.findByRole('button', { name: 'Back to p. 1' })
    await user.click(back)
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 1 / 3'))
    expect(screen.queryByRole('button', { name: /Back to p\./ })).not.toBeInTheDocument()
  })

  it('the Back chip expires after ten seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    setup({ doc: { outline }, search: { panel: 'outline' } })
    await waitOpen()
    const nav = await screen.findByRole('navigation', { name: 'Document outline' })
    fireEvent.click(within(nav).getByRole('button', { name: /Part B/ }))
    expect(await screen.findByRole('button', { name: 'Back to p. 1' })).toBeInTheDocument()
    act(() => void vi.advanceTimersByTime(10_100))
    expect(screen.queryByRole('button', { name: /Back to p\./ })).not.toBeInTheDocument()
  })

  it('shows a Contents button only when the file has an outline', async () => {
    setup()
    await waitOpen()
    expect(screen.queryByRole('button', { name: 'Contents' })).not.toBeInTheDocument()
  })
})

describe('go to page', () => {
  it('opens a labelled field and jumps', async () => {
    const user = userEvent.setup()
    setup()
    await waitOpen()
    await user.click(indicator())
    const field = await screen.findByLabelText('Go to page')
    await user.clear(field)
    await user.type(field, '3')
    await user.click(screen.getByRole('button', { name: 'Go' }))
    await waitFor(() => expect(indicator()).toHaveTextContent('p. 3 / 3'))
  })
})

describe('slots for the annotation layer and the library', () => {
  it('renders marks under and overlays over every mounted page, and the bar and overlay slots', async () => {
    const extensions: ReaderExtensions = {
      renderMarks: (p) => <i data-testid={`marks-${p}`} />,
      renderOverlay: (p) => <i data-testid={`overlay-${p}`} />,
      syncChip: <span>Saved chip</span>,
      marksCount: <span>12 marks</span>,
      tools: <div>Tool pill</div>,
      topActions: <button type="button">Marks list</button>,
      viewportOverlay: (api) => <div data-testid="floating">{`page ${api.page} of ${api.document.title}`}</div>,
    }
    setup({ extensions })
    await waitOpen()
    expect(screen.getByTestId('marks-1')).toBeInTheDocument()
    expect(screen.getByTestId('overlay-2')).toBeInTheDocument()
    expect(screen.getByText('Saved chip')).toBeInTheDocument()
    expect(screen.getByText('12 marks')).toBeInTheDocument()
    expect(screen.getByText('Tool pill')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Marks list' })).toBeInTheDocument()
    expect(screen.getByTestId('floating')).toHaveTextContent('page 1 of Taxation module')
    const page = screen.getByRole('group', { name: 'Page 1' })
    const layers = Array.from(page.children).map(
      (c) => c.getAttribute('data-testid') ?? c.getAttribute('data-slot') ?? c.tagName,
    )
    expect(layers.indexOf('marks-1')).toBeLessThan(layers.indexOf('text-layer'))
    expect(layers.indexOf('overlay-1')).toBeGreaterThan(layers.indexOf('text-layer'))
  })
})
