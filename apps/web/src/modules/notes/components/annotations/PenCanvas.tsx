import { cn } from '@artha/design-system'
import { type PointerEvent as ReactPointerEvent, useCallback, useEffect, useRef } from 'react'

import type { InkColor } from '../../lib/annotation-types'
import { fromViewportPoint, type Viewport } from '../../lib/coords'
import type { TimedPoint } from '../../lib/ink-session'
import { initialPenState, type PenEffect, type PenSettings, type PointerKind, stepPen } from '../../lib/pen-input'
import { INK_STROKE } from './mark-styles'

export interface PenCanvasProps {
  width: number
  height: number
  rotation?: number
  color: InkColor
  /** Stroke width as a fraction of the page width. */
  strokeWidth: number
  fingerDraws: boolean
  /** A finished stroke: every sampled point in the stored frame (the caller simplifies it) and when it started and ended. */
  onStroke: (points: TimedPoint[], strokeWidth: number) => void
  /** The pointer type seen, for the device class of analytics. */
  onInput?: (pointerType: string) => void
}

const kindOf = (type: string): PointerKind => (type === 'pen' ? 'pen' : type === 'mouse' ? 'mouse' : 'touch')
const SCROLLER = '[data-slot="pdf-viewport"]'

/**
 * The pen's capture surface for one page (FR-F03-23). Pointer Events with pointer capture and coalesced samples, so a
 * fast stroke has no gaps; the stroke is painted straight into an SVG path (no React render per point), which keeps the
 * ink under the nib. Which pointers draw is decided by `stepPen` (stylus and mouse draw; a finger scrolls unless "finger
 * draws" is on, then two fingers scroll; palms are ignored). `touch-action` lets a finger scroll the page, and switches
 * to `none` as soon as a stylus is near so the page does not move under the pen.
 */
export function PenCanvas({
  width,
  height,
  rotation = 0,
  color,
  strokeWidth,
  fingerDraws,
  onStroke,
  onInput,
}: PenCanvasProps) {
  const surface = useRef<HTMLDivElement>(null)
  const path = useRef<SVGPathElement>(null)
  const machine = useRef(initialPenState())
  const raw = useRef<Array<{ x: number; y: number; t: number }>>([])
  const frame = useRef(0)
  const settings = useRef<PenSettings>({ fingerDraws })
  settings.current = { fingerDraws }
  const latest = useRef({ width, height, rotation, strokeWidth, onStroke })
  latest.current = { width, height, rotation, strokeWidth, onStroke }

  const paint = useCallback(() => {
    frame.current = 0
    const el = path.current
    if (!el) return
    const pts = raw.current
    const first = pts[0]
    el.setAttribute(
      'd',
      first
        ? `M${first.x} ${first.y}${pts
            .slice(1)
            .map((p) => `L${p.x} ${p.y}`)
            .join('')}${pts.length === 1 ? 'l0.01 0' : ''}`
        : '',
    )
  }, [])
  const paintSoon = useCallback(() => {
    if (!frame.current) frame.current = requestAnimationFrame(paint)
  }, [paint])
  useEffect(() => () => cancelAnimationFrame(frame.current), [])

  const clear = useCallback(() => {
    raw.current = []
    path.current?.setAttribute('d', '')
  }, [])

  const run = useCallback(
    (effect: PenEffect, target: HTMLElement) => {
      if (effect.type === 'begin') {
        raw.current = [{ x: effect.x, y: effect.y, t: effect.t }]
        paintSoon()
      } else if (effect.type === 'point') {
        raw.current.push({ x: effect.x, y: effect.y, t: effect.t })
        paintSoon()
      } else if (effect.type === 'end') {
        const { width: w, height: h, rotation: r, strokeWidth: sw, onStroke: emit } = latest.current
        const view: Viewport = { width: w, height: h, rotation: r }
        const points = raw.current.map((p): TimedPoint => {
          const [x, y] = fromViewportPoint([p.x, p.y], view)
          return { x, y, t: p.t }
        })
        clear()
        if (points.length > 0) emit(points, sw)
      } else if (effect.type === 'discard') {
        clear()
      } else {
        target.closest<HTMLElement>(SCROLLER)?.scrollBy({ left: effect.dx, top: effect.dy })
      }
    },
    [clear, paintSoon],
  )

  const handle = (phase: 'down' | 'move' | 'up' | 'cancel' | 'hover') => (e: ReactPointerEvent<HTMLDivElement>) => {
    const el = surface.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const kind = kindOf(e.pointerType)
    if (phase === 'down' || phase === 'hover') onInput?.(e.pointerType)
    // A stylus near the glass: stop the page panning under it (a finger down turns panning back on).
    if (kind === 'pen' && !settings.current.fingerDraws) el.style.touchAction = 'none'
    if (kind === 'touch' && phase === 'down' && !settings.current.fingerDraws) el.style.touchAction = ''
    const samples =
      phase === 'move' && e.nativeEvent.getCoalescedEvents
        ? e.nativeEvent.getCoalescedEvents().length > 0
          ? e.nativeEvent.getCoalescedEvents()
          : [e.nativeEvent]
        : [e.nativeEvent]
    let claim: 'draw' | 'ignore' | 'pass' = 'pass'
    for (const s of samples) {
      const step = stepPen(
        machine.current,
        {
          phase,
          id: e.pointerId,
          kind,
          x: s.clientX - rect.left,
          y: s.clientY - rect.top,
          t: s.timeStamp,
          contact: Math.max(s.width || 0, s.height || 0),
        },
        settings.current,
      )
      machine.current = step.state
      claim = step.claim
      for (const effect of step.effects) run(effect, el)
    }
    if (claim === 'pass') return
    // Ours (or a palm): the page's own tap and pinch handling must not see it.
    e.stopPropagation()
    if (e.cancelable) e.preventDefault()
    if (claim === 'draw' && phase === 'down') el.setPointerCapture?.(e.pointerId)
  }

  return (
    <div
      ref={surface}
      data-slot="pen-canvas"
      onPointerDown={handle('down')}
      onPointerMove={(e) => handle(e.buttons === 0 && e.pointerType === 'pen' ? 'hover' : 'move')(e)}
      onPointerUp={handle('up')}
      onPointerCancel={handle('cancel')}
      onPointerOver={(e) => e.pointerType === 'pen' && handle('hover')(e)}
      onContextMenu={(e) => e.preventDefault()}
      style={{ touchAction: fingerDraws ? 'none' : 'pan-x pan-y pinch-zoom' }}
      className="pointer-events-auto absolute inset-0 z-10 cursor-crosshair select-none"
    >
      <svg width={width} height={height} className="pointer-events-none absolute inset-0" fill="none" aria-hidden>
        <path
          ref={path}
          className={cn(INK_STROKE[color])}
          strokeWidth={Math.max(1, strokeWidth * (rotation % 180 === 0 ? width : height))}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}
