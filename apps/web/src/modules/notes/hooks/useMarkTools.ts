import { useCallback, useRef, useState } from 'react'

import { noteDeviceInput } from '../lib/annotation-analytics'
import type { InkColor, MarkRecord, MarkupColor } from '../lib/annotation-types'
import type { Rect } from '../lib/geometry'
import { hitTest } from '../lib/hit-test'
import {
  addStroke,
  finishStroke,
  type InkDrawing,
  inkGeometry,
  redoStroke,
  type TimedPoint,
  undoStroke,
} from '../lib/ink-session'
import {
  areaDraft,
  bookmarkDraft,
  clampFontSize,
  inkDraft,
  PEN_WIDTHS,
  type PenWidth,
  pinDraft,
  textBoxDraft,
  textBoxRect,
} from '../lib/mark-drafts'
import type { ReaderTool } from '../lib/reader-schema'
import type { MarksController } from './useAnnotations'

const TAP_REACH = 0.02

export interface MarkToolsOptions {
  marks: MarksController
  tool: ReaderTool | undefined
  defaultColor: MarkupColor
  /** A mark that needs words right now (pin, bookmark): opens the edit sheet with the caret in the comment. */
  onNeedsWords: (id: string) => void
  /** A mark was added by the student (reading-session count). */
  onAdded: () => void
}

/**
 * The tools that make marks on the page: colours and pen width, the pen's drawing in progress (strokes within two seconds
 * join one drawing, with undo and redo), pins, bookmarks, areas, text boxes and the eraser. The marks themselves come
 * from `useAnnotations`; this decides what a pen stroke or a tap means.
 */
export function useMarkTools({ marks, defaultColor, onNeedsWords, onAdded }: MarkToolsOptions) {
  const [markupColor, setMarkupColor] = useState<MarkupColor | null>(null)
  const [inkColor, setInkColor] = useState<InkColor>('i1')
  const [penWidth, setPenWidth] = useState<PenWidth>('medium')
  const [drawing, setDrawingState] = useState<InkDrawing | null>(null)
  const drawingRef = useRef<InkDrawing | null>(null)
  const setDrawing = (next: InkDrawing | null) => {
    drawingRef.current = next
    setDrawingState(next)
  }
  const color = markupColor ?? defaultColor

  const [boxId, setBoxId] = useState<string | null>(null)

  const onStroke = useCallback(
    (page: number, points: TimedPoint[], width: number) => {
      const stroke = finishStroke(points, width)
      if (!stroke) return
      const { drawing: next, created } = addStroke(drawingRef.current, {
        page,
        color: inkColor,
        stroke,
        newId: () => '',
      })
      if (created) {
        const draft = inkDraft(page, inkGeometry(next.strokes).strokes, inkColor)
        const record = draft ? marks.add(draft, { tool: 'pen' }) : null
        if (!record) return
        onAdded()
        setDrawing({ ...next, markId: record.id })
      } else {
        marks.edit(next.markId, { geometry: { ...inkGeometry(next.strokes) } })
        setDrawing(next)
      }
    },
    [marks, inkColor, onAdded],
  )

  const undo = useCallback(() => {
    const current = drawingRef.current
    if (!current) return
    const { drawing: next, removed } = undoStroke(current)
    if (!removed) return
    if (next.strokes.length === 0) marks.remove(next.markId, { silent: true })
    else marks.edit(next.markId, { geometry: { ...inkGeometry(next.strokes) } })
    setDrawing(next)
  }, [marks])

  const redo = useCallback(() => {
    const current = drawingRef.current
    if (!current || current.redo.length === 0) return
    const next = redoStroke(current)
    if (current.strokes.length === 0) marks.restore(next.markId)
    marks.edit(next.markId, { geometry: { ...inkGeometry(next.strokes) } })
    setDrawing(next)
  }, [marks])

  const onTap = useCallback(
    (tool: ReaderTool | undefined, page: number, pt: [number, number]) => {
      if (tool === 'eraser') {
        const hit = hitTest(marks.marks, page, pt, [TAP_REACH, TAP_REACH])
        if (hit) marks.remove(hit.id)
        return
      }
      if (tool === 'text') {
        const draft = textBoxDraft(page, textBoxRect(pt), inkColor)
        const record = draft ? marks.add(draft, { tool: 'tap' }) : null
        if (record) {
          onAdded()
          setBoxId(record.id)
        }
        return
      }
      if (tool === 'sticky') {
        const draft = pinDraft(page, pt, color)
        const record = draft ? marks.add(draft, { tool: 'tap' }) : null
        if (record) {
          onAdded()
          onNeedsWords(record.id)
        }
        return
      }
      if (tool === 'bookmark') {
        const draft = bookmarkDraft(page, pt[1])
        const record = draft ? marks.add(draft, { tool: 'tap' }) : null
        if (record) {
          onAdded()
          onNeedsWords(record.id)
        }
      }
    },
    [marks, color, inkColor, onAdded, onNeedsWords],
  )

  const onArea = useCallback(
    (page: number, rect: Rect) => {
      const draft = areaDraft(page, rect, color)
      if (draft && marks.add(draft, { tool: 'area' })) onAdded()
    },
    [marks, color, onAdded],
  )

  const resizeBox = useCallback(
    (id: string, patch: { rect?: Rect; fs?: number }) => {
      const mark: MarkRecord | undefined = marks.find(id)
      if (!mark) return
      const g = mark.geometry as { rect: Rect; fs: number }
      marks.edit(id, {
        geometry: { rect: patch.rect ?? g.rect, fs: patch.fs === undefined ? g.fs : clampFontSize(patch.fs) },
      })
    },
    [marks],
  )

  return {
    markupColor: color,
    setMarkupColor,
    inkColor,
    setInkColor,
    penWidth,
    setPenWidth,
    penWidthValue: PEN_WIDTHS[penWidth],
    ink: { canUndo: (drawing?.strokes.length ?? 0) > 0, canRedo: (drawing?.redo.length ?? 0) > 0, undo, redo },
    onStroke,
    onTap,
    onArea,
    boxId,
    setBoxId,
    resizeBox,
    onInput: noteDeviceInput,
  }
}
