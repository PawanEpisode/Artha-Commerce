import { useEffect } from 'react'

import { AnnotationLayer } from '../components/annotations/AnnotationLayer'
import { inkOf } from '../components/annotations/mark-styles'
import { PenCanvas } from '../components/annotations/PenCanvas'
import { TextBoxEditor } from '../components/annotations/TextBoxEditor'
import { type SurfaceTool, ToolSurface } from '../components/annotations/ToolSurface'
import { usePdfPageContext } from '../components/reader/PdfPageContext'
import type { Rect } from '../lib/geometry'
import { usePageScope } from './annotation-scope'

/** Highlights, underlines and areas of one page, under its text (the reader's `renderMarks` slot). */
export function PageMarks({ page }: { page: number }) {
  const scope = usePageScope()
  const ctx = usePdfPageContext()
  const register = scope?.registerText
  const text = ctx.text
  // The page's text (native or OCR) is what "highlight this search hit" anchors to.
  useEffect(() => {
    register?.(page, text)
    return () => register?.(page, null)
  }, [register, page, text])
  const marks = scope?.byPage.get(page)
  if (!scope || !marks || marks.length === 0) return null
  return (
    <AnnotationLayer
      layer="under"
      marks={marks}
      width={ctx.width}
      height={ctx.height}
      selectedId={scope.selectedId}
      pulse={scope.pulse}
      legend={scope.legend}
    />
  )
}

const SURFACE: Record<string, SurfaceTool | undefined> = {
  text: 'text',
  sticky: 'sticky',
  bookmark: 'bookmark',
  area: 'area',
  eraser: 'eraser',
}

/** Ink, pins, flags and text boxes of one page, above its text, with the active tool's capture surface (`renderOverlay`). */
export function PageOverlay({ page }: { page: number }) {
  const scope = usePageScope()
  const ctx = usePdfPageContext()
  if (!scope) return null
  const all = scope.byPage.get(page) ?? []
  const box = scope.boxId ? all.find((m) => m.id === scope.boxId) : undefined
  const shown = box ? all.filter((m) => m.id !== box.id) : all
  const surface = scope.tool ? SURFACE[scope.tool] : undefined
  const geometry = box?.geometry as { rect: Rect; fs: number } | undefined
  return (
    <>
      <AnnotationLayer
        layer="over"
        marks={shown}
        width={ctx.width}
        height={ctx.height}
        selectedId={scope.selectedId}
        pulse={scope.pulse}
        legend={scope.legend}
        onSelect={scope.onSelectMark}
      />
      {scope.tool === 'pen' ? (
        <PenCanvas
          width={ctx.width}
          height={ctx.height}
          color={scope.inkColor}
          strokeWidth={scope.penWidth}
          fingerDraws={scope.fingerDraws}
          onStroke={(points, width) => scope.onStroke(page, points, width)}
          onInput={scope.onInput}
        />
      ) : null}
      {surface ? (
        <ToolSurface
          tool={surface}
          width={ctx.width}
          height={ctx.height}
          color={scope.markupColor}
          onTap={(pt) => scope.onTap(page, pt)}
          onArea={(rect) => scope.onArea(page, rect)}
          onInput={scope.onInput}
        />
      ) : null}
      {box && geometry ? (
        <TextBoxEditor
          width={ctx.width}
          height={ctx.height}
          rect={geometry.rect}
          fs={geometry.fs}
          text={scope.boxText}
          color={inkOf(box.color)}
          onTextChange={scope.onBoxText}
          onRectChange={scope.onBoxRect}
          onFontSizeChange={scope.onBoxFont}
          onDone={scope.onBoxDone}
          onDelete={scope.onBoxDelete}
        />
      ) : null}
    </>
  )
}
