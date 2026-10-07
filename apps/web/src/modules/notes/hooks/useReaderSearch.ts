import { useEffect, useMemo, useState } from 'react'

import type { SearchResultView, SearchStatus } from '../components/reader/ReaderSearchPanel'
import type { PdfDocumentHandle } from '../lib/pdf-engine'
import { searchLocally } from '../lib/pdf-engine/local-search'
import { MIN_QUERY } from '../lib/pdf-engine/search-match'
import { useInDocumentSearch } from './useDocuments'

export const SEARCH_DEBOUNCE_MS = 250

/** The value after it has stopped changing for `ms`. */
export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}

export interface ReaderSearchState {
  results: SearchResultView[]
  status: SearchStatus
  progress: { done: number; total: number } | null
  truncated: boolean
  note: string | null
}

export interface UseReaderSearchOptions {
  docId: string
  handle: PdfDocumentHandle | null
  query: string
  /** `local` reads the pages in the browser; `server` asks the API (large files, scanned files). */
  mode: 'local' | 'server'
  enabled: boolean
  /** Text extraction of the file is locked or skipped, so the server has nothing to search. */
  locked?: boolean
}

/** One interface over the two search paths (ERD 6.3 and PRD 5.5): same results shape, same states. */
export function useReaderSearch({
  docId,
  handle,
  query,
  mode,
  enabled,
  locked,
}: UseReaderSearchOptions): ReaderSearchState {
  const q = useDebounced(query.trim(), SEARCH_DEBOUNCE_MS)
  const active = enabled && q.length >= MIN_QUERY

  const [local, setLocal] = useState<ReaderSearchState>({
    results: [],
    status: 'idle',
    progress: null,
    truncated: false,
    note: null,
  })
  useEffect(() => {
    if (mode !== 'local' || !active || !handle) {
      setLocal({ results: [], status: 'idle', progress: null, truncated: false, note: null })
      return
    }
    const controller = new AbortController()
    setLocal((s) => ({ ...s, status: 'searching', progress: { done: 0, total: handle.pageCount } }))
    void searchLocally(handle, q, {
      signal: controller.signal,
      onProgress: (done, total) => setLocal((s) => ({ ...s, progress: { done, total } })),
      onHits: (hits) => setLocal((s) => ({ ...s, results: hits.map((h) => ({ page: h.page, snippet: h.snippet })) })),
    }).then((r) => {
      if (r.aborted) return
      setLocal({
        results: r.hits.map((h) => ({ page: h.page, snippet: h.snippet })),
        status: 'done',
        progress: null,
        truncated: r.truncated,
        note: null,
      })
    })
    return () => controller.abort()
  }, [mode, active, handle, q])

  const server = useInDocumentSearch(docId, q, mode === 'server' && active && !locked)
  const serverState = useMemo<ReaderSearchState>(() => {
    const data = server.data
    const results = (data?.items ?? []).map((i) => ({ page: i.page, snippet: i.snippet }))
    const partial = data && data.indexed_pages < data.page_count
    return {
      results,
      status: server.isError ? 'error' : server.isFetching ? 'searching' : data ? 'done' : 'idle',
      progress: null,
      truncated: results.length >= 50,
      note: locked
        ? 'This PDF is locked, so search is not available.'
        : partial
          ? `Search covers ${data.indexed_pages} of ${data.page_count} pages so far.`
          : null,
    }
  }, [server.data, server.isError, server.isFetching, locked])

  if (!active) return { results: [], status: 'idle', progress: null, truncated: false, note: null }
  if (mode === 'server') return locked ? { ...serverState, status: 'done' } : serverState
  return local
}
