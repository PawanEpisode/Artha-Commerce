import { mergeAdjacentQuads } from './geometry'
import type { PdfTextContent } from './pdf-engine'
import { findMatches } from './pdf-engine/search-match'
import { type PageSelection, rectsForRange, selectionFor } from './pdf-engine/text-layer'

/**
 * A search hit as a selection (FR-F03-71, the keyboard path): the `ordinal`-th match of `query` on a page, with its line
 * rectangles and quote, so "Highlight this result" saves the same mark a drag over the words would. Null when the page
 * no longer has that match (the text changed, or the page text is not loaded).
 */
export function selectionForHit(
  page: number,
  content: PdfTextContent,
  query: string,
  ordinal: number,
): PageSelection | null {
  const match = findMatches(content.text, query)[ordinal]
  if (!match) return null
  const rects = mergeAdjacentQuads(rectsForRange(content.items, match.start, match.end))
  if (rects.length === 0) return null
  return selectionFor(page, content, { start: match.start, end: match.end }, rects)
}
