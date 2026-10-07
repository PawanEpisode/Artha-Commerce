/**
 * Search inside the open document with the text the browser already extracts (small documents). Large documents use the
 * server (`GET documents/{id}/search/`) instead, because reading hundreds of pages in the browser is slow and heavy.
 */
import type { PdfDocumentHandle } from './index'
import { findMatches, snippetAround } from './search-match'

export interface LocalHit {
  page: number
  start: number
  end: number
  snippet: string
}

export interface LocalSearchOptions {
  signal?: AbortSignal
  /** Stop after this many hits (the list shows the first 50). */
  limit?: number
  /** Pages scanned so far and the total, for a progress line. */
  onProgress?: (done: number, total: number) => void
  /** Pages with hits so far, so the panel fills in as the scan goes. */
  onHits?: (hits: LocalHit[]) => void
}

export interface LocalSearchResult {
  hits: LocalHit[]
  /** True when the scan stopped at `limit` before the last page. */
  truncated: boolean
  aborted: boolean
}

export async function searchLocally(
  doc: Pick<PdfDocumentHandle, 'pageCount' | 'getPageText'>,
  query: string,
  { signal, limit = 50, onProgress, onHits }: LocalSearchOptions = {},
): Promise<LocalSearchResult> {
  const hits: LocalHit[] = []
  for (let page = 1; page <= doc.pageCount; page++) {
    if (signal?.aborted) return { hits, truncated: false, aborted: true }
    let text = ''
    try {
      text = await doc.getPageText(page)
    } catch {
      // A page that cannot be read has no hits; the scan goes on.
    }
    for (const m of findMatches(text, query)) {
      hits.push({ page, start: m.start, end: m.end, snippet: snippetAround(text, m) })
      if (hits.length >= limit) {
        onHits?.(hits.slice())
        return { hits, truncated: true, aborted: false }
      }
    }
    onProgress?.(page, doc.pageCount)
    if (page % 5 === 0 || page === doc.pageCount) onHits?.(hits.slice())
  }
  return { hits, truncated: false, aborted: false }
}
