import { createContext, type MutableRefObject, type ReactNode, useContext } from 'react'

import type { useAnnotationConflicts } from '../hooks/useAnnotationConflicts'
import type { MarksController } from '../hooks/useAnnotations'
import type { ReaderSettings } from '../hooks/useReaderSettings'
import type { Legend } from '../lib/annotation-legend'
import type { InkColor, MarkRecord, MarkupColor } from '../lib/annotation-types'
import type { Rect } from '../lib/geometry'
import type { TimedPoint } from '../lib/ink-session'
import type { PenWidth } from '../lib/mark-drafts'
import type { PdfTextContent } from '../lib/pdf-engine'
import type { PageSelection } from '../lib/pdf-engine/text-layer'
import type { ReaderSearch, ReaderTool } from '../lib/reader-schema'
import type { ReaderApi } from './reader-extensions'

/**
 * What the pages need: the marks by page and the handlers of the active tool. Changes only when marks, the tool or its
 * options change (never on a text selection), so a drag over text does not redraw every page.
 */
export interface PageScope {
  byPage: ReadonlyMap<number, readonly MarkRecord[]>
  legend: Legend
  selectedId: string | null
  pulse: { id: string; nonce: number } | null
  tool: ReaderTool | undefined
  markupColor: MarkupColor
  inkColor: InkColor
  penWidth: number
  fingerDraws: boolean
  /** The text box being typed in (drawn by its editor, not by the layer). */
  boxId: string | null
  boxText: string
  onSelectMark: (id: string) => void
  onTap: (page: number, point: [number, number]) => void
  onArea: (page: number, rect: Rect) => void
  onStroke: (page: number, points: TimedPoint[], width: number) => void
  onInput: (pointerType: string) => void
  onBoxText: (text: string) => void
  onBoxRect: (rect: Rect) => void
  onBoxFont: (fs: number) => void
  onBoxDone: () => void
  onBoxDelete: () => void
  registerText: (page: number, content: PdfTextContent | null) => void
}

export interface EditTarget {
  id: string
  /** Put the caret in the comment field on open (a new pin or bookmark). */
  focusComment: boolean
  /** Made a moment ago: an empty pin is discarded when the sheet closes. */
  fresh: boolean
}

/** Everything the floating pieces need (toolbars, sheets, the list). Free to change often. */
export interface UiScope {
  marks: MarksController
  settings: ReaderSettings
  search: ReaderSearch
  setSearch: (patch: Partial<ReaderSearch>) => void
  apiRef: MutableRefObject<ReaderApi | null>
  docId: string
  tool: ReaderTool | undefined
  setTool: (tool: ReaderTool | undefined) => void
  markupColor: MarkupColor
  setMarkupColor: (key: MarkupColor) => void
  inkColor: InkColor
  setInkColor: (key: InkColor) => void
  penWidth: PenWidth
  setPenWidth: (width: PenWidth) => void
  ink: { canUndo: boolean; canRedo: boolean; undo: () => void; redo: () => void }
  selection: PageSelection | null
  selectionActions: {
    color: (key: MarkupColor) => void
    underline: () => void
    note: () => void
    card: () => void
    copy: () => void
    dismiss: () => void
  }
  selectedMark: MarkRecord | null
  markActions: {
    color: (key: MarkRecord['color'] & string) => void
    edit: () => void
    card: () => void
    remove: () => void
    dismiss: () => void
  }
  edit: EditTarget | null
  openEdit: (id: string, options?: { focusComment?: boolean }) => void
  closeEdit: () => void
  listOpen: boolean
  setListOpen: (open: boolean) => void
  goToMark: (id: string) => void
  conflicts: ReturnType<typeof useAnnotationConflicts>
  conflictOpen: boolean
  setConflictOpen: (open: boolean) => void
  /** The reader shows a page (reading-session analytics). */
  onPage: (page: number) => void
  /** Wide screens dock the list beside the page; phones use a sheet. */
  docked: boolean
}

const PageScopeContext = createContext<PageScope | null>(null)
const UiScopeContext = createContext<UiScope | null>(null)

export function AnnotationProvider({ page, ui, children }: { page: PageScope; ui: UiScope; children: ReactNode }) {
  return (
    <PageScopeContext.Provider value={page}>
      <UiScopeContext.Provider value={ui}>{children}</UiScopeContext.Provider>
    </PageScopeContext.Provider>
  )
}

/** Null outside the annotation layer: a reader without it draws no marks. */
export const usePageScope = () => useContext(PageScopeContext)
export const useUiScope = () => useContext(UiScopeContext)
