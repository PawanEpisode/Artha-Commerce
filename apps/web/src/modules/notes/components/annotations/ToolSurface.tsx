import { cn } from '@artha/design-system'
import { type PointerEvent as ReactPointerEvent, useRef, useState } from 'react'

import type { MarkupColor } from '../../lib/annotation-types'
import { fromViewportPoint, type Viewport } from '../../lib/coords'
import type { Rect } from '../../lib/geometry'
import { rectFromDrag } from '../../lib/mark-drafts'
import { HL_BORDER, HL_FILL } from './mark-styles'

export type SurfaceTool = 'text' | 'sticky' | 'bookmark' | 'area' | 'eraser'

export interface ToolSurfaceProps {
  tool: SurfaceTool
  width: number
  height: number
  rotation?: number
  color: MarkupColor
  /** A tap or click in the stored frame (text box, pin, bookmark, eraser). */
  onTap: (point: [number, number]) => void
  /** A finished drag in the stored frame (area). */
  onArea: (rect: Rect) => void
  onInput?: (pointerType: string) => void
}

const TAP_SLOP = 8
const TAP_MS = 600
const CURSOR: Record<SurfaceTool, string> = {
  text: 'cursor-text',
  sticky: 'cursor-copy',
  bookmark: 'cursor-copy',
  area: 'cursor-crosshair',
  eraser: 'cursor-pointer',
}

/**
 * The capture surface of the tools that act on a point or a rectangle. It sits above the page's text, so while one is
 * active the page cannot be selected (leave with Escape or Select). A tap still lets a finger scroll the page; the
 * area tool takes the touch (`touch-action: none`) because dragging is its whole job.
 */
export function ToolSurface({ tool, width, height, rotation = 0, color, onTap, onArea, onInput }: ToolSurfaceProps) {
  const surface = useRef<HTMLDivElement>(null)
  const start = useRef<{ x: number; y: number; t: number; id: number } | null>(null)
  const [drag, setDrag] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const view: Viewport = { width, height, rotation }

  const local = (e: ReactPointerEvent) => {
    const rect = surface.current?.getBoundingClientRect()
    return { x: e.clientX - (rect?.left ?? 0), y: e.clientY - (rect?.top ?? 0) }
  }
  const stored = (x: number, y: number) => fromViewportPoint([x, y], view)

  const onDown = (e: ReactPointerEvent) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return
    onInput?.(e.pointerType)
    const p = local(e)
    start.current = { ...p, t: e.timeStamp, id: e.pointerId }
    if (tool === 'area') {
      surface.current?.setPointerCapture?.(e.pointerId)
      setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
      e.stopPropagation()
    }
  }
  const onMove = (e: ReactPointerEvent) => {
    if (tool !== 'area' || !start.current || start.current.id !== e.pointerId) return
    const p = local(e)
    setDrag((d) => (d ? { ...d, x1: p.x, y1: p.y } : d))
  }
  const onUp = (e: ReactPointerEvent) => {
    const s = start.current
    start.current = null
    if (!s || s.id !== e.pointerId) return
    const p = local(e)
    if (tool === 'area') {
      setDrag(null)
      const a = stored(s.x, s.y)
      const b = stored(p.x, p.y)
      const rect = rectFromDrag(a, b)
      if (rect) onArea(rect)
      return
    }
    if (Math.hypot(p.x - s.x, p.y - s.y) > TAP_SLOP || e.timeStamp - s.t > TAP_MS) return
    onTap(stored(p.x, p.y))
  }

  const box = drag && {
    left: Math.min(drag.x0, drag.x1),
    top: Math.min(drag.y0, drag.y1),
    width: Math.abs(drag.x1 - drag.x0),
    height: Math.abs(drag.y1 - drag.y0),
  }

  return (
    <div
      ref={surface}
      data-slot="tool-surface"
      data-tool={tool}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={() => {
        start.current = null
        setDrag(null)
      }}
      style={{ touchAction: tool === 'area' ? 'none' : 'pan-x pan-y pinch-zoom' }}
      className={cn('pointer-events-auto absolute inset-0 z-10 select-none', CURSOR[tool])}
    >
      {box ? (
        <span
          aria-hidden
          style={box}
          className={cn('mark-blend absolute rounded-md border-2 border-dashed', HL_FILL[color], HL_BORDER[color])}
        />
      ) : null}
    </div>
  )
}
