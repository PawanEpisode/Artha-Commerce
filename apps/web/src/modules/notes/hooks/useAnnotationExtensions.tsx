import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { type EditTarget, type PageScope, type UiScope } from '../containers/annotation-scope'
import { MarksCountButton, MarksListButton, MarksSyncChip, MarksTools } from '../containers/AnnotationChrome'
import { AnnotationSidePanel, AnnotationViewportOverlay } from '../containers/AnnotationViewportOverlay'
import { PageMarks, PageOverlay } from '../containers/PageMarks'
import type { ReaderApi, ReaderExtensions } from '../containers/reader-extensions'
import { markNotify } from '../lib/annotation-notify'
import type { ColorKey, MarkKind, MarkRecord, MarkupColor } from '../lib/annotation-types'
import { linkFromSelection } from '../lib/chapter-link'
import { hitTest } from '../lib/hit-test'
import { markupDraft } from '../lib/mark-drafts'
import { consumeOpenedFrom } from '../lib/opened-from'
import type { PdfTextContent } from '../lib/pdf-engine'
import type { PageSelection } from '../lib/pdf-engine/text-layer'
import type { ReaderSearch } from '../lib/reader-schema'
import { selectionForHit } from '../lib/search-hit'
import { useAnnotationConflicts } from './useAnnotationConflicts'
import { useAnnotations } from './useAnnotations'
import { useDocument } from './useDocuments'
import { useMarkNavigation } from './useMarkNavigation'
import { useMarkTools } from './useMarkTools'
import { useMediaQuery } from './useMediaQuery'
import { useReaderSettings } from './useReaderSettings'
import { useReadingSession } from './useReadingSession'
import { useStable } from './useStable'

const COMMIT_MS = 600
const IDLE_APPLY_MS = 800
const TAP_REACH_PX = 10
const EMPTY_LINK = linkFromSelection(null)

const clearBrowserSelection = () => window.getSelection()?.removeAllRanges()

export interface AnnotationExtensionsArgs {
  docId: string
  search: ReaderSearch
  onSearchChange: (patch: Partial<ReaderSearch>) => void
}

/**
 * Builds the annotation layer's part of the reader: the `ReaderExtensions` (stable, so the pages do not redraw when the
 * tool or a selection changes) and two context values the pieces read: `page` for the pages, `ui` for everything floating.
 * The URL keeps `tool`, `ann` and `panel`; local state keeps the selection, the open sheets and the pen's drawing.
 */
export function useAnnotationExtensions({ docId, search, onSearchChange }: AnnotationExtensionsArgs) {
  const document = useDocument(docId).data
  const settings = useReaderSettings()
  const marks = useAnnotations(
    { id: docId, ranges: document?.ranges ?? [], link: document?.link ?? EMPTY_LINK },
    !!document?.file_url,
  )
  const conflicts = useAnnotationConflicts(marks)
  const session = useReadingSession()
  const docked = useMediaQuery('(min-width: 768px)')
  const apiRef = useRef<ReaderApi | null>(null)
  const openedFrom = useRef(consumeOpenedFrom(search)).current

  const tool = search.tool
  const ann = search.ann
  const [selection, setSelection] = useState<PageSelection | null>(null)
  const selectionRef = useRef<PageSelection | null>(null)
  selectionRef.current = selection
  const [edit, setEdit] = useState<EditTarget | null>(null)
  const [conflictOpen, setConflictOpen] = useState(false)
  const texts = useRef(new Map<number, PdfTextContent>())

  const setSearch = useStable(onSearchChange)
  const select = useStable((id: string | undefined) => setSearch({ ann: id }))
  const openEdit = useStable((id: string, options?: { focusComment?: boolean }) => {
    setEdit({ id, focusComment: options?.focusComment ?? false, fresh: false })
    clearBrowserSelection()
  })

  // ---- Tools ------------------------------------------------------------------------------------------------------------
  const tools = useMarkTools({
    marks,
    tool,
    defaultColor: settings.defaultColor,
    onNeedsWords: (id) => setEdit({ id, focusComment: true, fresh: true }),
    onAdded: session.onMarkAdded,
  })

  // Text boxes are typed into on the page: a local draft, committed 600 ms after the last key and when the box is left.
  const { boxId, setBoxId, resizeBox } = tools
  const [boxText, setBoxText] = useState('')
  const boxTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestBox = useRef({ boxId, boxText, marks })
  latestBox.current = { boxId, boxText, marks }
  const flushBox = useStable(() => {
    if (boxTimer.current) clearTimeout(boxTimer.current)
    boxTimer.current = null
    const { boxId: id, boxText: text, marks: controller } = latestBox.current
    const mark = id ? controller.find(id) : undefined
    if (id && mark && mark.comment !== text) controller.edit(id, { comment: text })
  })
  useEffect(() => {
    setBoxText(boxId ? (marks.find(boxId)?.comment ?? '') : '')
    // Only when a different box opens; typing must not reset the draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boxId])
  useEffect(() => () => flushBox(), [flushBox])

  const boxHandlers = {
    onBoxText: useStable((text: string) => {
      setBoxText(text)
      latestBox.current.boxText = text
      if (boxTimer.current) clearTimeout(boxTimer.current)
      boxTimer.current = setTimeout(flushBox, COMMIT_MS)
    }),
    onBoxRect: useStable((rect: [number, number, number, number]) => boxId && resizeBox(boxId, { rect })),
    onBoxFont: useStable((fs: number) => boxId && resizeBox(boxId, { fs })),
    onBoxDone: useStable(() => {
      flushBox()
      const empty = latestBox.current.boxText.trim() === ''
      if (boxId && empty) marks.remove(boxId, { silent: true })
      setBoxId(null)
    }),
    onBoxDelete: useStable(() => {
      if (boxId) marks.remove(boxId)
      setBoxId(null)
    }),
  }

  const setTool = useStable((next: typeof tool) => {
    flushBox()
    setBoxId(null)
    clearBrowserSelection()
    setSelection(null)
    setSearch({ tool: next, ann: undefined })
  })

  // ---- Selection to marks -----------------------------------------------------------------------------------------------
  const addMarkup = (
    sel: PageSelection,
    kind: 'highlight' | 'underline',
    color: MarkupColor,
    via: 'selection' = 'selection',
  ) => {
    const draft = markupDraft(sel, kind, color)
    const record = draft ? marks.add(draft, { tool: via }) : null
    if (record) session.onMarkAdded()
    return record
  }
  const finishSelection = () => {
    clearBrowserSelection()
    setSelection(null)
  }
  const fromSelection = (kind: 'highlight' | 'underline', color: MarkupColor): MarkRecord | null => {
    const sel = selectionRef.current
    if (!sel) return null
    const record = addMarkup(sel, kind, color)
    finishSelection()
    return record
  }
  const selectionActions = {
    color: useStable((key: MarkupColor) => {
      tools.setMarkupColor(key)
      fromSelection('highlight', key)
    }),
    underline: useStable(() => void fromSelection('underline', tools.markupColor)),
    note: useStable(() => {
      const record = fromSelection('highlight', tools.markupColor)
      if (record) setEdit({ id: record.id, focusComment: true, fresh: false })
    }),
    card: useStable(() => {
      const record = fromSelection('highlight', tools.markupColor)
      if (record) void marks.makeCard(record.id)
    }),
    copy: useStable(() => {
      const text = selectionRef.current?.text
      if (!text) return
      void navigator.clipboard?.writeText(text).then(markNotify.copied, markNotify.copyFailed)
      finishSelection()
    }),
    dismiss: useStable(finishSelection),
  }

  // With the Highlight or Underline tool on, finishing a selection saves the mark at once (mouse up, or a pause for touch).
  const pointerDown = useRef(false)
  useEffect(() => {
    if (tool !== 'highlight' && tool !== 'underline') return
    let timer: ReturnType<typeof setTimeout> | undefined
    const apply = () => {
      if (!selectionRef.current) return
      const record = addMarkup(selectionRef.current, tool, tools.markupColor)
      if (record) finishSelection()
    }
    const down = () => {
      pointerDown.current = true
      clearTimeout(timer)
    }
    const up = () => {
      pointerDown.current = false
      clearTimeout(timer)
      timer = setTimeout(apply, 30)
    }
    window.document.addEventListener('pointerdown', down, true)
    window.document.addEventListener('pointerup', up, true)
    if (selection && !pointerDown.current) timer = setTimeout(apply, IDLE_APPLY_MS)
    return () => {
      clearTimeout(timer)
      window.document.removeEventListener('pointerdown', down, true)
      window.document.removeEventListener('pointerup', up, true)
    }
    // addMarkup and tools change identity each render; the effect reads the latest through the refs it closes over.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tool, selection, tools.markupColor])

  // ---- Marks: selection by tap, navigation, toolbar actions ---------------------------------------------------------------
  const selectedMark = useMemo(() => {
    const mark = ann ? marks.find(ann) : undefined
    return mark && !mark.deleted_at ? mark : null
  }, [ann, marks])
  useEffect(() => {
    if (ann && marks.status === 'ready' && !selectedMark) select(undefined)
  }, [ann, marks.status, selectedMark, select])

  const nav = useMarkNavigation({
    marks: marks.marks,
    selectedId: ann,
    currentPage: () => apiRef.current?.page ?? 1,
    goToPage: (p) => apiRef.current?.goToPage(p),
    select: (id) => select(id),
  })

  const live = useRef({ marks: marks.marks, ann, tool })
  live.current = { marks: marks.marks, ann, tool }
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (!target?.closest('[data-slot="pdf-viewport"]') || live.current.tool) return
      if (target.closest('a, button, input, textarea, select, [role="dialog"], [data-slot="floating-toolbar"]')) return
      const sel = window.getSelection()
      if (sel && !sel.isCollapsed) return
      const pageEl = target.closest<HTMLElement>('[data-page]')
      const box = pageEl?.getBoundingClientRect()
      if (!pageEl || !box || box.width === 0 || box.height === 0) return
      const point: [number, number] = [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height]
      const hit = hitTest(live.current.marks, Number(pageEl.dataset.page), point, [
        TAP_REACH_PX / box.width,
        TAP_REACH_PX / box.height,
      ])
      if (hit) select(hit.id)
      else if (live.current.ann) select(undefined)
    }
    window.document.addEventListener('click', onClick)
    return () => window.document.removeEventListener('click', onClick)
  }, [select])

  const markActions = {
    color: useStable((key: ColorKey) => selectedMark && marks.edit(selectedMark.id, { color: key })),
    edit: useStable(() => {
      if (!selectedMark) return
      if (selectedMark.kind === 'textbox') {
        select(undefined)
        setBoxId(selectedMark.id)
      } else openEdit(selectedMark.id)
    }),
    card: useStable(() => selectedMark && void marks.makeCard(selectedMark.id)),
    remove: useStable(() => {
      if (!selectedMark) return
      marks.remove(selectedMark.id)
      select(undefined)
    }),
    dismiss: useStable(() => select(undefined)),
  }

  // ---- Search hit to highlight ---------------------------------------------------------------------------------------------
  const highlightHit = useStable(async (hit: { page: number; ordinal: number; query: string }) => {
    let content: PdfTextContent | null | undefined = texts.current.get(hit.page)
    if (!content) {
      try {
        content = await apiRef.current?.engine?.getPage(hit.page).getText()
      } catch {
        content = null
      }
    }
    const sel = content ? selectionForHit(hit.page, content, hit.query, hit.ordinal) : null
    const record = sel ? addMarkup(sel, 'highlight', tools.markupColor) : null
    if (record) markNotify.highlightedHit(hit.page)
    else markNotify.hitNotFound()
  })

  // ---- Keys ---------------------------------------------------------------------------------------------------------------
  const onKeyDown = useStable((event: React.KeyboardEvent): boolean => {
    const has = !!selectionRef.current
    switch (event.key) {
      case 'h':
      case 'u':
        if (!has) return false
        event.preventDefault()
        fromSelection(event.key === 'h' ? 'highlight' : 'underline', settings.defaultColor)
        return true
      case 'n':
        event.preventDefault()
        if (has) selectionActions.note()
        else setTool('sticky')
        return true
      case '[':
      case ']':
        event.preventDefault()
        if (!nav.step(event.key === ']' ? 1 : -1)) markNotify.noMarks()
        return true
      case 'Delete':
      case 'Backspace':
        if (!live.current.ann || live.current.tool) return false
        event.preventDefault()
        marks.remove(live.current.ann)
        select(undefined)
        return true
      default:
        return false
    }
  })

  // ---- What the pages and floating pieces read ------------------------------------------------------------------------------
  const byPage = useMemo(() => {
    const map = new Map<number, MarkRecord[]>()
    for (const m of marks.marks) map.set(m.page, [...(map.get(m.page) ?? []), m])
    return map
  }, [marks.marks])

  const onSelectMark = useStable((id: string) => select(id))
  const onTap = useStable((page: number, pt: [number, number]) => tools.onTap(tool, page, pt))
  const onArea = useStable(tools.onArea)
  const onStroke = useStable(tools.onStroke)
  const onInput = useStable(tools.onInput)
  const registerText = useCallback((page: number, content: PdfTextContent | null) => {
    if (content) texts.current.set(page, content)
    else texts.current.delete(page)
  }, [])

  const page: PageScope = useMemo(
    () => ({
      byPage,
      legend: settings.legend,
      selectedId: ann ?? null,
      pulse: nav.pulse,
      tool,
      markupColor: tools.markupColor,
      inkColor: tools.inkColor,
      penWidth: tools.penWidthValue,
      fingerDraws: settings.fingerDraws,
      boxId,
      boxText,
      onSelectMark,
      onTap,
      onArea,
      onStroke,
      onInput,
      ...boxHandlers,
      registerText,
    }),
    // The box handlers and the others above are stable; everything else is data.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      byPage,
      settings.legend,
      settings.fingerDraws,
      ann,
      nav.pulse,
      tool,
      tools.markupColor,
      tools.inkColor,
      tools.penWidthValue,
      boxId,
      boxText,
    ],
  )

  const ui: UiScope = {
    marks,
    settings,
    search,
    setSearch,
    apiRef,
    docId,
    tool,
    setTool,
    markupColor: tools.markupColor,
    setMarkupColor: tools.setMarkupColor,
    inkColor: tools.inkColor,
    setInkColor: tools.setInkColor,
    penWidth: tools.penWidth,
    setPenWidth: tools.setPenWidth,
    ink: tools.ink,
    selection,
    selectionActions,
    selectedMark,
    markActions,
    edit,
    openEdit,
    closeEdit: () => setEdit(null),
    listOpen: search.panel === 'annotations',
    setListOpen: (open) => setSearch({ panel: open ? 'annotations' : undefined }),
    goToMark: nav.goToMark,
    conflicts,
    conflictOpen,
    setConflictOpen,
    onPage: session.onPage,
    docked,
  }

  const onSelection = useStable((next: PageSelection | null) => setSelection(next))
  const extensions = useMemo<ReaderExtensions>(
    () => ({
      renderMarks: (p) => <PageMarks page={p} />,
      renderOverlay: (p) => <PageOverlay page={p} />,
      syncChip: <MarksSyncChip />,
      marksCount: <MarksCountButton />,
      tools: <MarksTools />,
      topActions: <MarksListButton />,
      viewportOverlay: (api) => <AnnotationViewportOverlay api={api} />,
      sidePanel: <AnnotationSidePanel />,
      onSelection,
      onKeyDown,
      onHighlightHit: (hit) => void highlightHit(hit),
      openedFrom,
    }),
    [onSelection, onKeyDown, highlightHit, openedFrom],
  )

  return { extensions, page, ui, ready: !!document }
}

export type { MarkKind }
