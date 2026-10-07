import type { KeyboardEvent, ReactNode } from 'react'

import type { DocumentDetail, PageTone } from '../lib/document-types'
import type { PdfDocumentHandle } from '../lib/pdf-engine'
import type { PageSelection } from '../lib/pdf-engine/text-layer'
import type { ReaderSearch, ZoomSpec } from '../lib/reader-schema'

/** What the reader tells the layers it hosts. Read-only, except the two functions. */
export interface ReaderApi {
  document: DocumentDetail
  /** The open file, or null while it opens. */
  engine: PdfDocumentHandle | null
  /** Current page (1-based) and zoom. */
  page: number
  zoom: ZoomSpec
  tone: PageTone
  /** The URL state: `tool` and `ann` belong to the annotation layer. */
  search: ReaderSearch
  /** Scrolls to a page (the Back chip remembers where the student was). */
  goToPage: (page: number) => void
  /** Merges into the URL (replace, never a new history entry): `tool`, `ann`, `panel`, `q`. */
  setSearch: (patch: Partial<ReaderSearch>) => void
  online: boolean
}

/**
 * The seams the annotation layer (WEB-2) and the library (WEB-3) plug into without touching the reader:
 *  - `renderMarks(page)`: drawn on every mounted page UNDER the text layer: highlights, underlines, area boxes. Use
 *    `usePdfPageContext()` for the page's size and `lib/coords.ts` for rectangles; `pointer-events-none`, `mark-blend`.
 *  - `renderOverlay(page)`: drawn ABOVE the text layer: ink, pins, text boxes and the tool's capture surface.
 *  - `syncChip`: left of the page number in the bottom bar (the `SyncChip`); `marksCount`: right of it.
 *  - `tools`: a row above the scrubber (the tool pill).
 *  - `viewportOverlay(api)`: floating UI over the reading area (the selection toolbar, the mark editor).
 *  - `onSelection`: a text selection inside one page (see `PageSelection`), or null when it is gone.
 *  - `topActions`: extra buttons in the top bar (for example the marks list).
 */
export interface ReaderExtensions {
  renderMarks?: (page: number) => ReactNode
  renderOverlay?: (page: number) => ReactNode
  syncChip?: ReactNode
  marksCount?: ReactNode
  tools?: ReactNode
  topActions?: ReactNode
  viewportOverlay?: (api: ReaderApi) => ReactNode
  onSelection?: (selection: PageSelection | null) => void
  /** Offered every key press that is not in a field, before the reader's own keys (so `n` can mean "note"). Return true to claim it. */
  onKeyDown?: (event: KeyboardEvent) => boolean | void
  /** "Highlight this result" in the search panel: the page, the hit's position on it and the query. */
  onHighlightHit?: (hit: { page: number; ordinal: number; query: string }) => void
  /** Where the PDF was opened from, for the `pdf_opened` event. */
  openedFrom?: 'library' | 'search' | 'aggregate' | 'chapter'
  /** A panel docked to the right of the reading area from `md` up (the marks list). Below that it is the layer's own sheet. */
  sidePanel?: ReactNode
}
