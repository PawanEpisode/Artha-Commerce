import { cn } from '@artha/design-system'
import { type CSSProperties, memo, useEffect, useMemo, useRef } from 'react'

import type { PdfTextContent } from '../../lib/pdf-engine'
import {
  type Endpoint,
  itemStyle,
  MAX_LAYER_ITEMS,
  type PageSelection,
  rectsToFrame,
  selectionFor,
  selectionOffsets,
} from '../../lib/pdf-engine/text-layer'

let measureCtx: CanvasRenderingContext2D | null | undefined
const emCache = new Map<string, number>()

/** Width of `text` in a 1 px sans-serif font, cached. Null where there is no canvas (tests), so runs are not stretched. */
function measureEm(text: string): number {
  if (measureCtx === undefined) {
    try {
      const jsdom = typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)
      measureCtx = jsdom ? null : document.createElement('canvas').getContext('2d')
      if (measureCtx) measureCtx.font = '100px sans-serif'
    } catch {
      measureCtx = null
    }
  }
  if (!measureCtx) return 0
  const hit = emCache.get(text)
  if (hit !== undefined) return hit
  const em = measureCtx.measureText(text).width / 100
  if (emCache.size > 20_000) emCache.clear()
  emCache.set(text, em)
  return em
}

/** The run element and character offset an endpoint of a DOM selection falls in, or null outside the layer. */
function endpointOf(layer: HTMLElement, node: Node, offset: number): Endpoint | null {
  if (!layer.contains(node)) return null
  if (node === layer) {
    const spans = layer.querySelectorAll<HTMLElement>('[data-start]')
    const at = spans[Math.min(offset, spans.length - 1)]
    if (!at) return null
    const after = offset >= spans.length
    return { runStart: Number(at.dataset.start), offset: after ? (at.textContent?.length ?? 0) : 0 }
  }
  const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element)
  const span = el?.closest<HTMLElement>('[data-start]')
  if (!span || !layer.contains(span)) return null
  // An element endpoint counts children: 0 is the start of the run, anything else its end.
  const chars = node.nodeType === Node.TEXT_NODE ? offset : offset > 0 ? (span.textContent?.length ?? 0) : 0
  return { runStart: Number(span.dataset.start), offset: chars }
}

export interface TextLayerProps {
  content: PdfTextContent
  page: number
  /** Page size in points. */
  pageW: number
  pageH: number
  /** Page height on screen, CSS pixels: the runs' font sizes follow it. */
  height: number
  /** `ocr` is the invisible layer of a scan (`aria-label` says so). */
  kind?: 'native' | 'ocr'
  /** Called when the selection inside this page changes (null when it is gone). */
  onSelection?: (selection: PageSelection | null) => void
  className?: string
}

/**
 * The invisible, selectable text of one page over its canvas. Runs are placed from `PdfTextContent` (pdf.js text or OCR
 * words), so one component serves both and a screen reader reads the page as ordinary text. Marks are never drawn here.
 */
export const TextLayer = memo(function TextLayer({
  content,
  page,
  pageW,
  pageH,
  height,
  kind = 'native',
  onSelection,
  className,
}: TextLayerProps) {
  const ref = useRef<HTMLDivElement>(null)
  const runs = useMemo(
    () =>
      content.items.slice(0, MAX_LAYER_ITEMS).map((item, i, all) => {
        // The space or line break that follows a run in the page text rides along inside the run, so reading the
        // layer (a screen reader, a copy) gives words with their spaces. Offsets stay those of the page text.
        const end = item.start + item.str.length
        const gap = content.text.slice(end, all[i + 1]?.start ?? content.text.length)
        const shown = /^\s*$/.test(gap) ? item.str + gap : item.str
        const s = itemStyle(item, pageW, pageH, measureEm)
        const transform = [
          s.angle ? `rotate(${s.angle}rad)` : '',
          s.scaleX !== 1 ? `scaleX(${s.scaleX.toFixed(3)})` : '',
        ]
          .filter(Boolean)
          .join(' ')
        const style: CSSProperties = {
          left: `${(s.left * 100).toFixed(3)}%`,
          top: `${(s.top * 100).toFixed(3)}%`,
          fontSize: `calc(var(--text-layer-h) * ${s.fontFraction})`,
          ...(transform ? { transform } : {}),
        }
        return (
          <span
            key={i}
            data-start={item.start}
            style={style}
            className="absolute origin-top-left cursor-text whitespace-pre"
          >
            {shown}
          </span>
        )
      }),
    [content, pageW, pageH],
  )

  useEffect(() => {
    if (!onSelection) return
    let frame = 0
    let reported = false
    const report = () => {
      frame = 0
      const layer = ref.current
      const sel = window.getSelection()
      if (!layer || !sel || sel.rangeCount === 0 || sel.isCollapsed) {
        if (reported) onSelection(null)
        reported = false
        return
      }
      const range = sel.getRangeAt(0)
      const a = endpointOf(layer, range.startContainer, range.startOffset)
      const b = endpointOf(layer, range.endContainer, range.endOffset)
      const offsets = a && b ? selectionOffsets(a, b) : null
      if (!offsets) {
        if (reported) onSelection(null)
        reported = false
        return
      }
      reported = true
      const box = layer.getBoundingClientRect()
      onSelection(selectionFor(page, content, offsets, rectsToFrame(Array.from(range.getClientRects()), box)))
    }
    const onChange = () => {
      if (!frame) frame = requestAnimationFrame(report)
    }
    document.addEventListener('selectionchange', onChange)
    return () => {
      document.removeEventListener('selectionchange', onChange)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [onSelection, content, page])

  return (
    <div
      ref={ref}
      data-slot="text-layer"
      data-kind={kind}
      style={{ '--text-layer-h': `${height}px` } as CSSProperties}
      className={cn(
        'absolute inset-0 overflow-hidden leading-none text-transparent select-text selection:bg-primary/35 selection:text-transparent',
        className,
      )}
    >
      {runs}
    </div>
  )
})
