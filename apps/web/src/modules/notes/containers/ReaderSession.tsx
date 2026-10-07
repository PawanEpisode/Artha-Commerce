import { Alert, Button, ListTree, Search, toast, useTheme, ZoomIn, ZoomOut } from '@artha/design-system'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { track } from '~/modules/observability'
import { useOnline } from '~/modules/personalization'

import { LargeDocumentNotice } from '../components/reader/LargeDocumentNotice'
import { OutlinePanel } from '../components/reader/OutlinePanel'
import { PageScrubber } from '../components/reader/PageScrubber'
import { NightToneHint, PageToneMenu } from '../components/reader/PageToneMenu'
import { PasswordDialog } from '../components/reader/PasswordDialog'
import { type PageExtras, PdfViewport, type ViewportHandle } from '../components/reader/PdfViewport'
import { ReaderChrome, TOP_BAR_PX } from '../components/reader/ReaderChrome'
import { ReaderErrorState } from '../components/reader/ReaderErrorState'
import { ReaderSearchPanel } from '../components/reader/ReaderSearchPanel'
import { ScannedBanner } from '../components/reader/ScannedBanner'
import { useDocumentProcessing, useOcrPages, useUpdateProgress } from '../hooks/useDocuments'
import { usePdfDocument } from '../hooks/usePdfDocument'
import { useReaderChrome } from '../hooks/useReaderChrome'
import { useDebounced, useReaderSearch } from '../hooks/useReaderSearch'
import { type DocumentDetail, type PageTone } from '../lib/document-types'
import { requestIdOf } from '../lib/errors'
import { isLargeDocument } from '../lib/large-document'
import type { PdfEngine } from '../lib/pdf-engine'
import { clampPage, type PageBox } from '../lib/reader-layout'
import { resolveResume } from '../lib/reader-resume'
import type { ReaderSearch, ZoomSpec } from '../lib/reader-schema'
import {
  defaultTone,
  needsOcrBanner,
  pagesBucket,
  searchMode,
  shouldSuggestNight,
  ttfpBucket,
} from '../lib/reader-state'
import { formatStoredZoom } from '../lib/reader-zoom'
import type { ReaderApi, ReaderExtensions } from './reader-extensions'

const A4: PageBox = { w: 595, h: 842 }
/** Room the bars take above the first page and below the last. */
const PAD_TOP = TOP_BAR_PX + 8
const PAD_BOTTOM = 112
const BACK_CHIP_MS = 10_000
const URL_SYNC_MS = 600

const store = (kind: 'local' | 'session') => {
  try {
    return kind === 'local' ? window.localStorage : window.sessionStorage
  } catch {
    return null
  }
}
const readFlag = (kind: 'local' | 'session', key: string) => store(kind)?.getItem(key) === '1'
const writeFlag = (kind: 'local' | 'session', key: string) => {
  try {
    store(kind)?.setItem(key, '1')
  } catch {
    // Storage can be blocked; the hint then shows again next time, which is harmless.
  }
}

export interface ReaderSessionProps {
  doc: DocumentDetail
  search: ReaderSearch
  onSearchChange: (patch: Partial<ReaderSearch>) => void
  onBack: () => void
  /** Asks the API for a freshly signed file URL (after a 403 from storage). */
  refreshUrl: () => Promise<string>
  engine?: PdfEngine
  extensions?: ReaderExtensions
  /** Starts OCR for a scanned file (wired by the library slice, with its quota sheet). */
  onMakeSearchable?: () => void
}

/** The reader for one openable document: opens the file, owns zoom, page, search, bars and notices, saves progress. */
export function ReaderSession({
  doc,
  search,
  onSearchChange,
  onBack,
  refreshUrl,
  engine,
  extensions,
  onMakeSearchable,
}: ReaderSessionProps) {
  const online = useOnline()
  const { resolved } = useTheme()
  const mountedAt = useRef(performance.now())
  const viewport = useRef<ViewportHandle>(null)
  const root = useRef<HTMLDivElement>(null)
  const searchInput = useRef<HTMLInputElement>(null)

  // ---- Open the file ----------------------------------------------------------------------------------------------
  const fileUrl = useRef(doc.file_url ?? '')
  if (doc.file_url) fileUrl.current = doc.file_url
  const refresh = useCallback(async () => {
    fileUrl.current = await refreshUrl()
    return fileUrl.current
  }, [refreshUrl])
  const open = usePdfDocument({ engine, enabled: !!doc.file_url, getUrl: () => fileUrl.current, refreshUrl: refresh })
  const handle = open.state.phase === 'ready' ? open.state.handle : null

  useEffect(() => {
    performance.mark?.('notes-pdf-reader-mounted')
  }, [])
  useEffect(() => {
    if (open.state.phase === 'cancelled') onBack()
  }, [open.state.phase, onBack])

  // ---- Where we are -----------------------------------------------------------------------------------------------
  const resume = useRef(resolveResume(search, doc, doc.page_count)).current
  const [page, setPage] = useState(resume.page)
  const [zoom, setZoom] = useState<ZoomSpec>(resume.zoom)
  const [toneChoice, setToneChoice] = useState<PageTone | null>(doc.page_tone)
  const tone = toneChoice ?? defaultTone(resolved)
  const [jump, setJump] = useState<{ page: number; nonce: number } | null>(null)
  const [backTo, setBackTo] = useState<number | null>(null)
  const backTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const processing = useDocumentProcessing(doc.id, true)
  const live = processing.data
  const ocrStatus = live?.ocr_status ?? doc.ocr_status
  const ocrDone = live?.ocr_pages_done ?? doc.ocr_pages_done
  const ocrTotal = live?.ocr_pages_total ?? doc.ocr_pages_total
  const textStatus = live?.text_status ?? doc.text_status
  const isScanned = live?.is_scanned ?? doc.is_scanned

  const pageCount = handle?.pageCount ?? doc.page_count ?? doc.page_meta?.length ?? 0
  const large = isLargeDocument(doc.bytes, pageCount)

  // Page sizes: stored `page_meta` (no layout shift), or what the engine reports as pages come into range.
  const [learned, setLearned] = useState<Record<number, PageBox>>({})
  const sizes = useMemo<PageBox[]>(() => {
    const meta = doc.page_meta
    const fallback = meta?.[0] ?? learned[1] ?? A4
    return Array.from({ length: pageCount }, (_, i) => meta?.[i] ?? learned[i + 1] ?? fallback)
  }, [doc.page_meta, learned, pageCount])
  const [range, setRange] = useState<[number, number] | null>(null)
  const onWindowChange = useCallback(
    (next: [number, number] | null) => {
      setRange(next)
      if (!next || !handle || doc.page_meta) return
      for (let i = next[0]; i <= next[1]; i++) {
        if (learned[i + 1]) continue
        handle
          .getPageSize(i + 1)
          .then((s) => setLearned((prev) => (prev[i + 1] ? prev : { ...prev, [i + 1]: s })))
          .catch(() => undefined)
      }
    },
    [handle, doc.page_meta, learned],
  )

  // ---- Bars, panels, notices --------------------------------------------------------------------------------------
  const panel = search.panel
  const searchOpen = panel === 'search'
  const chrome = useReaderChrome(searchOpen)
  const [query, setQuery] = useState(search.q ?? '')
  const [activeHit, setActiveHit] = useState(-1)
  const mode = searchMode(large, isScanned)
  const found = useReaderSearch({
    docId: doc.id,
    handle,
    query,
    mode,
    enabled: searchOpen,
    locked: textStatus === 'locked',
  })
  const debouncedQuery = useDebounced(query.trim(), 250)

  const [scannedHidden, setScannedHidden] = useState(() => readFlag('session', `notes.reader.scanned.${doc.id}`))
  const [largeSeen, setLargeSeen] = useState(() => !large || readFlag('local', `notes.reader.large.${doc.id}`))
  const [nightSeen, setNightSeen] = useState(() => readFlag('local', 'notes.reader.night-hint'))
  const showNight = shouldSuggestNight(resolved, tone, nightSeen) && toneChoice === null
  const showLarge = large && !largeSeen
  useEffect(() => {
    if (showLarge) writeFlag('local', `notes.reader.large.${doc.id}`)
  }, [showLarge, doc.id])

  // ---- Moving around ----------------------------------------------------------------------------------------------
  const remember = useCallback((from: number) => {
    setBackTo(from)
    if (backTimer.current) clearTimeout(backTimer.current)
    backTimer.current = setTimeout(() => setBackTo(null), BACK_CHIP_MS)
  }, [])
  useEffect(() => () => void (backTimer.current && clearTimeout(backTimer.current)), [])

  const goToPage = useCallback(
    (target: number, options: { remember?: boolean } = {}) => {
      const next = clampPage(target, pageCount)
      if (options.remember !== false && next !== page) remember(page)
      setJump((j) => ({ page: next, nonce: (j?.nonce ?? 0) + 1 }))
    },
    [pageCount, page, remember],
  )
  const goBack = useCallback(() => {
    if (backTo) goToPage(backTo, { remember: false })
    setBackTo(null)
  }, [backTo, goToPage])

  // Progress and URL follow the page, zoom and tone; the URL is replaced, never pushed.
  const progress = useUpdateProgress(doc.id)
  useEffect(() => {
    progress.save({
      last_page: page,
      last_zoom: formatStoredZoom(zoom),
      ...(toneChoice ? { page_tone: toneChoice } : {}),
    })
  }, [page, zoom, toneChoice, progress])
  const pageUrl = useDebounced(page, URL_SYNC_MS)
  useEffect(() => {
    if (pageUrl !== search.page || zoom !== (search.zoom ?? undefined)) onSearchChange({ page: pageUrl, zoom })
    // The URL is an output here; reading `search` back would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageUrl, zoom])
  const urlQuery = useDebounced(query.trim() || undefined, 500)
  useEffect(() => {
    if (searchOpen && urlQuery !== search.q) onSearchChange({ q: urlQuery })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlQuery, searchOpen])

  // First paint: one performance mark for measuring, one product event with buckets only.
  const painted = useRef(false)
  const onPageDrawn = useCallback(() => {
    if (painted.current) return
    painted.current = true
    performance.mark?.('notes-pdf-first-page')
    const ms = performance.now() - mountedAt.current
    track('pdf_opened', {
      pages_bucket: pagesBucket(pageCount),
      source_kind: doc.source_kind,
      ttfp_ms_bucket: ttfpBucket(ms),
      large_mode: large,
      ...(extensions?.openedFrom ? { from: extensions.openedFrom } : {}),
    })
  }, [pageCount, doc.source_kind, large, extensions?.openedFrom])

  // ---- Search ----------------------------------------------------------------------------------------------------
  useEffect(() => setActiveHit(found.results.length > 0 ? 0 : -1), [found.results.length, debouncedQuery])
  const hit = found.results[activeHit]
  const ordinal = useMemo(() => {
    if (!hit) return null
    let n = 0
    for (let i = 0; i < activeHit; i++) if (found.results[i]?.page === hit.page) n += 1
    return n
  }, [hit, activeHit, found.results])
  const pickHit = useCallback(
    (index: number) => {
      const target = found.results[index]
      if (!target) return
      setActiveHit(index)
      goToPage(target.page)
    },
    [found.results, goToPage],
  )
  const stepHit = (delta: 1 | -1) => {
    const n = found.results.length
    if (n === 0) return
    pickHit((activeHit + delta + n) % n)
  }
  const openSearch = useCallback(() => {
    onSearchChange({ panel: 'search' })
    requestAnimationFrame(() => searchInput.current?.focus())
  }, [onSearchChange])
  const closeSearch = useCallback(() => {
    onSearchChange({ panel: undefined, q: undefined })
    viewport.current?.element()?.focus()
  }, [onSearchChange])

  // ---- Keys ------------------------------------------------------------------------------------------------------
  const onKeyDown = (e: React.KeyboardEvent) => {
    chrome.show()
    const target = e.target as HTMLElement
    const typing = target.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      openSearch()
      return
    }
    if (e.key === 'Escape') {
      if (searchOpen) closeSearch()
      else if (panel) onSearchChange({ panel: undefined })
      else if (search.tool) onSearchChange({ tool: undefined })
      return
    }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return
    if (extensions?.onKeyDown?.(e) === true) return
    switch (e.key) {
      case 'n':
      case 'j':
        e.preventDefault()
        goToPage(page + 1, { remember: false })
        break
      case 'p':
      case 'k':
        e.preventDefault()
        goToPage(page - 1, { remember: false })
        break
      case '+':
      case '=':
        e.preventDefault()
        viewport.current?.zoomIn()
        break
      case '-':
        e.preventDefault()
        viewport.current?.zoomOut()
        break
      case '0':
        e.preventDefault()
        viewport.current?.zoomFit()
        break
      case '/':
        e.preventDefault()
        openSearch()
        break
    }
  }

  // ---- Page extras -----------------------------------------------------------------------------------------------
  const ocrEnabled = isScanned === true && (ocrDone > 0 || ocrStatus === 'partial' || ocrStatus === 'done')
  const ocrOf = useOcrPages(doc.id, ocrEnabled, range)
  const hasHighlights = searchOpen && debouncedQuery.length >= 2
  const pageExtras = useCallback(
    (p: number): PageExtras => ({
      ocrContent: ocrEnabled ? ocrOf(p) : null,
      useNativeText: isScanned !== true,
      query: hasHighlights ? debouncedQuery : undefined,
      activeIndex: hit && hit.page === p ? ordinal : null,
      marks: extensions?.renderMarks?.(p),
      children: extensions?.renderOverlay?.(p),
    }),
    [ocrEnabled, ocrOf, isScanned, hasHighlights, debouncedQuery, hit, ordinal, extensions],
  )

  // ---- Zoom label ------------------------------------------------------------------------------------------------
  const zoomText = zoom === 'fit' ? 'Fit width' : `${zoom}%`

  const api: ReaderApi = {
    document: doc,
    engine: handle,
    page,
    zoom,
    tone,
    search,
    goToPage,
    setSearch: onSearchChange,
    online,
  }

  const report = () => {
    const details = [
      `phase: ${open.state.phase}`,
      open.state.phase === 'error' ? `code: ${open.state.error.code}` : '',
      `pages: ${pageCount}`,
      `bytes: ${doc.bytes}`,
      `status: ${doc.status}`,
      requestIdOf(open.state.phase === 'error' ? open.state.error : null) ?? '',
    ]
      .filter(Boolean)
      .join('\n')
    void navigator.clipboard?.writeText(details).then(
      () => toast.success('Details copied. Send them to support so we can look into it.'),
      () => toast.error('We could not copy the details.'),
    )
  }

  if (open.state.phase === 'error') {
    const code = open.state.error.code
    return (
      <ReaderErrorState
        message={
          code === 'invalid_pdf'
            ? 'The file looks damaged. Try downloading the original and opening it on your device.'
            : !online
              ? 'You are offline. Connect to the internet and try again.'
              : 'Something went wrong while loading the PDF. Please try again.'
        }
        onRetry={open.retry}
        downloadUrl={doc.file_url}
        onReport={report}
        onBack={onBack}
      />
    )
  }

  const needsScanBanner = needsOcrBanner(isScanned, ocrStatus) && !scannedHidden
  const notices = (
    <>
      {!online ? (
        <Alert variant="info">
          Offline: marks are saved on this device. Pages that are not loaded yet are not available.
        </Alert>
      ) : null}
      {textStatus === 'locked' && doc.is_encrypted ? (
        <Alert variant="info">Locked: search and OCR need the password. You can still read and mark the PDF.</Alert>
      ) : null}
      {needsScanBanner ? (
        <ScannedBanner
          status={ocrStatus}
          pagesDone={ocrDone}
          pagesTotal={ocrTotal}
          onMakeSearchable={onMakeSearchable}
          onDismiss={() => {
            writeFlag('session', `notes.reader.scanned.${doc.id}`)
            setScannedHidden(true)
          }}
        />
      ) : null}
      {showLarge ? <LargeDocumentNotice onDismiss={() => setLargeSeen(true)} /> : null}
      {showNight ? (
        <NightToneHint
          onAccept={() => {
            writeFlag('local', 'notes.reader.night-hint')
            setNightSeen(true)
            setToneChoice('night')
          }}
          onDismiss={() => {
            writeFlag('local', 'notes.reader.night-hint')
            setNightSeen(true)
          }}
        />
      ) : null}
      {searchOpen ? (
        <ReaderSearchPanel
          query={query}
          onQueryChange={setQuery}
          results={found.results}
          activeIndex={activeHit}
          status={found.status}
          progress={found.progress}
          truncated={found.truncated}
          note={found.note}
          onNext={() => stepHit(1)}
          onPrevious={() => stepHit(-1)}
          onPick={pickHit}
          onClose={closeSearch}
          onHighlight={
            extensions?.onHighlightHit
              ? () => {
                  if (hit && ordinal !== null)
                    extensions.onHighlightHit?.({ page: hit.page, ordinal, query: query.trim() })
                }
              : undefined
          }
          inputRef={searchInput}
        />
      ) : null}
    </>
  )

  return (
    // The wrapper only listens for keys that bubble up from the reading area and the bars; it is not a control itself.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div ref={root} onKeyDown={onKeyDown} data-slot="pdf-reader" data-phase={open.state.phase}>
      <ReaderChrome
        visible={chrome.visible}
        title={doc.title}
        subtitle={pageCount ? `${pageCount} pages` : undefined}
        onBack={onBack}
        notices={notices}
        side={extensions?.sidePanel}
        actions={
          <>
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              onClick={searchOpen ? closeSearch : openSearch}
              aria-label="Search in this PDF"
              aria-pressed={searchOpen}
              aria-keyshortcuts="/ Control+F"
            >
              <Search aria-hidden />
            </Button>
            {doc.outline && doc.outline.length > 0 ? (
              <Button
                variant="ghost"
                size="icon"
                className="size-11"
                onClick={() => onSearchChange({ panel: 'outline' })}
                aria-label="Contents"
              >
                <ListTree aria-hidden />
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon"
              className="hidden size-11 sm:inline-flex"
              onClick={() => viewport.current?.zoomOut()}
              aria-label="Zoom out"
              aria-keyshortcuts="-"
            >
              <ZoomOut aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="hidden min-h-11 min-w-16 tabular-nums sm:inline-flex"
              onClick={() => viewport.current?.zoomFit()}
              aria-label={`Zoom ${zoomText}. Fit width`}
              aria-keyshortcuts="0"
            >
              {zoomText}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="hidden size-11 sm:inline-flex"
              onClick={() => viewport.current?.zoomIn()}
              aria-label="Zoom in"
              aria-keyshortcuts="+"
            >
              <ZoomIn aria-hidden />
            </Button>
            <PageToneMenu tone={tone} onToneChange={setToneChoice} />
            {extensions?.topActions}
          </>
        }
        bottom={
          <>
            {extensions?.tools}
            <PageScrubber
              page={page}
              pageCount={pageCount}
              onGo={(p) => goToPage(p)}
              backTo={backTo}
              onBack={goBack}
              leftSlot={extensions?.syncChip}
              rightSlot={extensions?.marksCount}
              disabled={pageCount === 0}
            />
          </>
        }
      >
        <PdfViewport
          ref={viewport}
          doc={handle}
          sizes={sizes}
          zoom={zoom}
          tone={tone}
          initialPage={resume.page}
          jumpTo={jump}
          onPageChange={setPage}
          onZoomChange={setZoom}
          onScrollDirection={chrome.onScrollDirection}
          onTapMiddle={search.tool ? undefined : chrome.toggle}
          onWindowChange={onWindowChange}
          onPageDrawn={onPageDrawn}
          onSelection={extensions?.onSelection}
          onLink={(link) => {
            if (link.kind === 'internal') goToPage(link.page)
            else if (window.confirm(`This link leaves ArthaCommerce and opens ${link.url}. Open it?`))
              window.open(link.url, '_blank', 'noopener,noreferrer')
          }}
          pageExtras={pageExtras}
          coverUrl={doc.cover_url}
          large={large}
          offline={!online}
          padTop={PAD_TOP}
          padBottom={PAD_BOTTOM}
        />
        {extensions?.viewportOverlay?.(api)}
      </ReaderChrome>
      {doc.outline ? (
        <OutlinePanel
          open={panel === 'outline'}
          onOpenChange={(next) => onSearchChange({ panel: next ? 'outline' : undefined })}
          outline={doc.outline}
          currentPage={page}
          onGo={(p) => {
            onSearchChange({ panel: undefined })
            goToPage(p)
          }}
        />
      ) : null}
      <PasswordDialog
        open={open.prompt !== null}
        reason={open.prompt?.reason ?? 'need'}
        attempt={open.prompt?.attempt ?? 1}
        onSubmit={open.submitPassword}
        onCancel={open.cancelPassword}
      />
    </div>
  )
}
