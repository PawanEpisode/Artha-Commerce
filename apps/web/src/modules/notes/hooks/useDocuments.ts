import { keepPreviousData, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef } from 'react'

import { isOcrRunning, isPreparing, type PageText, type ProgressBody } from '../lib/document-types'
import { getDocument, getPagesText, getProcessing, putProgress, searchDocument } from '../lib/documents-api'
import { isFeatureDisabled, isNotFound } from '../lib/errors'
import { notesKeys } from '../lib/keys'
import type { PdfTextContent } from '../lib/pdf-engine'
import { ocrTextContent } from '../lib/pdf-engine/ocr-text-layer'

/** Pages of text the API returns per call (`pages/text/` allows at most 20). */
export const TEXT_CHUNK = 20
export const PROGRESS_DEBOUNCE_MS = 1500
export const PROCESSING_POLL_MS = 3000

/** A 404 or a switched-off flag will not change by asking again. */
const retryUnlessFinal = (failures: number, error: unknown) =>
  failures < 2 && !isNotFound(error) && !isFeatureDisabled(error)

/**
 * The document with its signed file URL (valid four hours). The reader never depends on the URL string itself (a
 * refetch signs a new one); it asks `useRefreshFileUrl` when a range request is refused.
 */
export function useDocument(id: string) {
  return useQuery({
    queryKey: notesKeys.document(id),
    queryFn: () => getDocument(id),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: retryUnlessFinal,
  })
}

/** A function that asks the API for a freshly signed file URL, for the range loader's retry after a 403. */
export function useRefreshFileUrl(id: string) {
  const client = useQueryClient()
  return useCallback(async () => {
    const fresh = await client.fetchQuery({
      queryKey: notesKeys.document(id),
      queryFn: () => getDocument(id),
      staleTime: 0,
    })
    if (!fresh.file_url) throw new Error('no file url')
    return fresh.file_url
  }, [client, id])
}

/**
 * Cheap poll of status, text extraction and OCR progress. Polls only while the server is still working (scanning,
 * inspecting, OCR queued or running), so an idle reader costs nothing. When preparing finishes the document is refetched
 * (it gains its file URL and page sizes); when OCR moves on the cached text pages are refetched (new word boxes).
 */
export function useDocumentProcessing(id: string, enabled = true) {
  const client = useQueryClient()
  const query = useQuery({
    queryKey: notesKeys.documentProcessing(id),
    queryFn: () => getProcessing(id),
    enabled,
    refetchInterval: (q) => {
      const d = q.state.data
      if (!d) return PROCESSING_POLL_MS
      return isPreparing(d.status) ||
        isOcrRunning(d.ocr_status) ||
        d.text_status === 'running' ||
        d.text_status === 'pending'
        ? PROCESSING_POLL_MS
        : false
    },
    retry: retryUnlessFinal,
  })
  const status = query.data?.status
  const ocrDone = query.data?.ocr_pages_done
  const lastStatus = useRef(status)
  const lastOcr = useRef(ocrDone)
  useEffect(() => {
    if (lastStatus.current !== undefined && status !== lastStatus.current)
      void client.invalidateQueries({ queryKey: notesKeys.document(id), exact: true })
    lastStatus.current = status
  }, [client, id, status])
  useEffect(() => {
    if (lastOcr.current !== undefined && ocrDone !== lastOcr.current)
      void client.invalidateQueries({ queryKey: ['notes', 'document', id, 'text'] })
    lastOcr.current = ocrDone
  }, [client, id, ocrDone])
  return query
}

const sameProgress = (a: ProgressBody | null, b: ProgressBody) =>
  a !== null &&
  a.last_page === b.last_page &&
  a.last_zoom === b.last_zoom &&
  (a.page_tone ?? null) === (b.page_tone ?? null)

/**
 * Saves the reading position. `save` is cheap and can be called on every scroll: the last value wins and goes out
 * after a pause (`PROGRESS_DEBOUNCE_MS`), when the tab is hidden, on `pagehide` (with `keepalive` so the request survives
 * the page) and when the reader unmounts. The endpoint is last-write-wins and idempotent, so repeats and reordering are
 * harmless; a failed save is dropped silently because the next change saves again.
 */
export function useUpdateProgress(id: string, enabled = true) {
  const client = useQueryClient()
  const pending = useRef<ProgressBody | null>(null)
  const sent = useRef<ProgressBody | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const flush = useCallback(
    (options: { keepalive?: boolean } = {}) => {
      if (timer.current) clearTimeout(timer.current)
      timer.current = null
      const body = pending.current
      pending.current = null
      if (!body || sameProgress(sent.current, body)) return
      sent.current = body
      putProgress(id, body, options)
        .then((result) =>
          client.setQueryData(notesKeys.document(id), (old: unknown) =>
            old && typeof old === 'object'
              ? {
                  ...old,
                  last_page: result.last_page,
                  last_zoom: result.last_zoom,
                  page_tone: result.page_tone,
                  last_opened_at: result.last_opened_at,
                }
              : old,
          ),
        )
        .catch(() => {
          sent.current = null
        })
    },
    [client, id],
  )

  const save = useCallback(
    (body: ProgressBody) => {
      if (!enabled) return
      pending.current = body
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => flush(), PROGRESS_DEBOUNCE_MS)
    },
    [enabled, flush],
  )

  useEffect(() => {
    const onHide = () => flush({ keepalive: true })
    const onVisibility = () => document.visibilityState === 'hidden' && onHide()
    window.addEventListener('pagehide', onHide)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('pagehide', onHide)
      document.removeEventListener('visibilitychange', onVisibility)
      flush()
    }
  }, [flush])

  return { save, flush }
}

/** Server search inside one document (large-document mode, or when the local scan is not possible). */
export function useInDocumentSearch(id: string, q: string, enabled = true) {
  const text = q.trim()
  return useQuery({
    queryKey: notesKeys.documentSearch(id, text),
    queryFn: () => searchDocument(id, text, 50),
    enabled: enabled && text.length >= 2,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    retry: retryUnlessFinal,
  })
}

/**
 * The server's text of the 20-page chunk holding `page`: OCR word boxes for the invisible text layer of a scan. Cached by
 * chunk, so scrolling through a chunk costs one request.
 */
export function usePageText(id: string, page: number, enabled = true) {
  const chunk = Math.floor((Math.max(1, page) - 1) / TEXT_CHUNK)
  const query = useQuery({
    queryKey: notesKeys.pageText(id, chunk),
    queryFn: () => getPagesText(id, chunk * TEXT_CHUNK + 1, chunk * TEXT_CHUNK + TEXT_CHUNK),
    enabled,
    staleTime: 5 * 60_000,
    retry: retryUnlessFinal,
  })
  const found: PageText | undefined = query.data?.pages.find((p) => p.page === page)
  return { page: found, isPending: query.isPending && enabled, isError: query.isError }
}

const ocrContentCache = new WeakMap<PageText, PdfTextContent | null>()
const contentOf = (page: PageText) => {
  if (!ocrContentCache.has(page)) ocrContentCache.set(page, ocrTextContent(page))
  return ocrContentCache.get(page) ?? null
}

/**
 * The invisible-text-layer content of OCR pages near the reader's window: fetches the 20-page chunks that overlap
 * `range` (0-based, inclusive) and returns a lookup `page (1-based) -> PdfTextContent | null` (null: no word boxes, so
 * the page has no OCR text yet). Disabled for documents that are not scanned.
 */
export function useOcrPages(id: string, enabled: boolean, range: [number, number] | null) {
  const chunks: number[] = []
  if (enabled && range) {
    for (let c = Math.floor(range[0] / TEXT_CHUNK); c <= Math.floor(range[1] / TEXT_CHUNK); c++) chunks.push(c)
  }
  const results = useQueries({
    queries: chunks.map((chunk) => ({
      queryKey: notesKeys.pageText(id, chunk),
      queryFn: () => getPagesText(id, chunk * TEXT_CHUNK + 1, chunk * TEXT_CHUNK + TEXT_CHUNK),
      staleTime: 5 * 60_000,
      retry: retryUnlessFinal,
    })),
  })
  const stamp = results.map((r) => r.dataUpdatedAt).join(',')
  return useMemo(() => {
    const byPage = new Map<number, PdfTextContent | null>()
    for (const r of results) for (const p of r.data?.pages ?? []) byPage.set(p.page, p.words ? contentOf(p) : null)
    return (page: number): PdfTextContent | null => byPage.get(page) ?? null
    // `stamp` changes exactly when any chunk's data does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stamp])
}
