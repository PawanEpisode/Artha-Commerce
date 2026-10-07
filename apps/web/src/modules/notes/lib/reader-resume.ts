import { clampPage } from './reader-layout'
import type { ReaderSearch, ZoomSpec } from './reader-schema'
import { parseStoredZoom } from './reader-zoom'

export interface ResumePoint {
  page: number
  zoom: ZoomSpec
}

/**
 * Where the reader opens: the URL (`?page=&zoom=`, a shared link or a mark opened from the notes list) wins over the
 * position stored on the document, which wins over the first page at fit width. Each part is decided on its own, so a
 * link with only `page` still resumes the stored zoom. A page past the end is clamped.
 */
export function resolveResume(
  search: Pick<ReaderSearch, 'page' | 'zoom'>,
  stored: { last_page: number; last_zoom: string },
  pageCount: number | null,
): ResumePoint {
  const count = pageCount ?? Number.MAX_SAFE_INTEGER
  return {
    page: clampPage(search.page ?? stored.last_page ?? 1, count),
    zoom: search.zoom ?? parseStoredZoom(stored.last_zoom),
  }
}
