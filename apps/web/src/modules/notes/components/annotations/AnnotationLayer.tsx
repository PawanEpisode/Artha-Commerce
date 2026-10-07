import { Bookmark, cn, StickyNote, SwatchShape } from '@artha/design-system'

import { type Legend } from '../../lib/annotation-legend'
import type { MarkRecord } from '../../lib/annotation-types'
import { toViewportPoint, toViewportRect, type Viewport } from '../../lib/coords'
import { geometryBbox, type Rect } from '../../lib/geometry'
import { describeMark } from '../../lib/mark-label'
import {
  HL_BORDER,
  HL_EDGE_TEXT,
  HL_FILL,
  HL_SOLID,
  INK_BORDER,
  INK_STROKE,
  INK_TEXT,
  inkOf,
  markupOf,
} from './mark-styles'

export interface AnnotationLayerProps {
  /** `under` goes in the reader's `renderMarks` slot (below the text, multiply blended), `over` in `renderOverlay`. */
  layer: 'under' | 'over'
  /** The marks of this one page. */
  marks: readonly MarkRecord[]
  /** The page box on screen, CSS pixels. */
  width: number
  height: number
  /** The student's view rotation, clockwise: 0, 90, 180 or 270. Stored geometry never changes with it. */
  rotation?: number
  selectedId?: string | null
  /** A mark just found from the list: a ring plays once (a still ring with reduced motion). A new `nonce` plays it again. */
  pulse?: { id: string; nonce: number } | null
  legend: Legend
  /** Pins, flags and text boxes take clicks (a mouse or finger on them selects the mark). */
  onSelect?: (id: string) => void
}

const UNDER = new Set<MarkRecord['kind']>(['highlight', 'underline', 'area'])
const px = (n: number) => Math.round(n * 100) / 100

/**
 * The marks of one page, drawn from normalised geometry at any zoom and rotation (`lib/coords.ts`). The canvas marks are
 * not focusable and are hidden from assistive technology: the annotation list is their accessible twin (PRD 11). Colour
 * is never the only signal: highlights carry a shape beside them, underlines a line, areas a dashed edge, pens have
 * names in the list.
 */
export function AnnotationLayer({
  layer,
  marks,
  width,
  height,
  rotation = 0,
  selectedId,
  pulse,
  legend,
  onSelect,
}: AnnotationLayerProps) {
  const view: Viewport = { width, height, rotation }
  const pulseOf = (id: string) => (pulse?.id === id ? pulse.nonce : 0)
  const mine = marks.filter((m) => !m.deleted_at && (layer === 'under' ? UNDER.has(m.kind) : true))
  const drawn = layer === 'under' ? mine : mine.filter((m) => !UNDER.has(m.kind))
  const selected = layer === 'over' ? mine.find((m) => m.id === selectedId) : undefined
  return (
    <div
      aria-hidden
      data-slot={layer === 'under' ? 'marks-under' : 'marks-over'}
      className={cn('pointer-events-none absolute inset-0', layer === 'under' && 'mark-blend')}
    >
      {layer === 'under'
        ? drawn.map((m) => (
            <MarkupMark key={`${m.id}:${pulseOf(m.id)}`} mark={m} view={view} pulsing={pulseOf(m.id) > 0} />
          ))
        : null}
      {layer === 'over' ? (
        <>
          <InkLayer marks={drawn.filter((m) => m.kind === 'ink')} view={view} pulse={pulse} />
          {drawn
            .filter((m) => m.kind === 'textbox')
            .map((m) => (
              <TextBoxMark
                key={`${m.id}:${pulseOf(m.id)}`}
                mark={m}
                view={view}
                legend={legend}
                pulsing={pulseOf(m.id) > 0}
                onSelect={onSelect}
              />
            ))}
          {drawn
            .filter((m) => m.kind === 'sticky')
            .map((m) => (
              <PinMark
                key={`${m.id}:${pulseOf(m.id)}`}
                mark={m}
                view={view}
                legend={legend}
                pulsing={pulseOf(m.id) > 0}
                onSelect={onSelect}
              />
            ))}
          {drawn
            .filter((m) => m.kind === 'bookmark')
            .map((m) => (
              <FlagMark
                key={`${m.id}:${pulseOf(m.id)}`}
                mark={m}
                view={view}
                legend={legend}
                pulsing={pulseOf(m.id) > 0}
                onSelect={onSelect}
              />
            ))}
          {selected ? <Outline mark={selected} view={view} /> : null}
        </>
      ) : null}
    </div>
  )
}

const place = (r: Rect) => ({ left: px(r[0]), top: px(r[1]), width: px(r[2]), height: px(r[3]) })

function MarkupMark({ mark, view, pulsing }: { mark: MarkRecord; view: Viewport; pulsing: boolean }) {
  const key = markupOf(mark.color)
  const rects: Rect[] =
    mark.kind === 'area' ? [(mark.geometry as { rect: Rect }).rect] : (mark.geometry as { quads: Rect[] }).quads
  const boxes = rects.map((r) => toViewportRect(r, view))
  const first = boxes[0]
  return (
    <>
      {boxes.map((box, i) => (
        <span
          key={i}
          data-mark-id={mark.id}
          data-kind={mark.kind}
          data-color={key}
          style={place(box)}
          className={cn(
            'absolute rounded-[2px]',
            mark.kind === 'highlight' && cn(HL_FILL[key], 'border-b', HL_BORDER[key]),
            mark.kind === 'underline' && cn('border-b-2', HL_BORDER[key]),
            mark.kind === 'area' && cn(HL_FILL[key], 'rounded-md border-2 border-dashed', HL_BORDER[key]),
            pulsing && 'mark-pulse',
          )}
        />
      ))}
      {first ? (
        <span
          data-mark-glyph={mark.id}
          style={{ left: Math.max(0, px(first[0]) - 12), top: px(first[1]) }}
          className={cn('absolute size-2.5', HL_EDGE_TEXT[key])}
        >
          <SwatchShape swatch={key} />
        </span>
      ) : null}
    </>
  )
}

/** The path of a stroke in pixels. A single point is a dot (a round cap on a zero-length segment). */
export function strokePath(pts: ReadonlyArray<[number, number]>, view: Viewport): string {
  const points = pts.map((p) => toViewportPoint(p, view))
  const [first, ...rest] = points
  if (!first) return ''
  if (rest.length === 0) return `M${px(first[0])} ${px(first[1])}l0.01 0`
  return `M${px(first[0])} ${px(first[1])}${rest.map((p) => `L${px(p[0])} ${px(p[1])}`).join('')}`
}

/** A stored stroke width (a fraction of the page's stored width) in pixels at this view. */
export const strokeWidthPx = (w: number, view: Viewport) => w * (view.rotation % 180 === 0 ? view.width : view.height)

function InkLayer({
  marks,
  view,
  pulse,
}: {
  marks: readonly MarkRecord[]
  view: Viewport
  pulse?: { id: string; nonce: number } | null
}) {
  if (marks.length === 0) return null
  return (
    <svg
      data-slot="ink"
      width={view.width}
      height={view.height}
      viewBox={`0 0 ${view.width} ${view.height}`}
      className="absolute inset-0"
      fill="none"
    >
      {marks.map((m) => {
        const key = inkOf(m.color)
        const strokes = (m.geometry as { strokes: Array<{ pts: Array<[number, number]>; w: number }> }).strokes
        return (
          <g
            key={`${m.id}:${pulse?.id === m.id ? pulse.nonce : 0}`}
            data-mark-id={m.id}
            data-kind="ink"
            data-color={key}
            className={cn(INK_STROKE[key], pulse?.id === m.id && 'mark-pulse')}
          >
            {strokes.map((s, i) => (
              <path
                key={i}
                d={strokePath(s.pts, view)}
                strokeWidth={Math.max(1, strokeWidthPx(s.w, view))}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}
          </g>
        )
      })}
    </svg>
  )
}

function TextBoxMark({
  mark,
  view,
  legend,
  pulsing,
  onSelect,
}: {
  mark: MarkRecord
  view: Viewport
  legend: Legend
  pulsing: boolean
  onSelect?: (id: string) => void
}) {
  const key = inkOf(mark.color)
  const { rect, fs } = mark.geometry as { rect: Rect; fs?: number }
  // The box keeps its stored size and turns with the view: size from the stored frame, centre from the viewed one.
  const stored = view.rotation % 180 === 0 ? [view.width, view.height] : [view.height, view.width]
  const centre = toViewportRect(rect, view)
  const cx = centre[0] + centre[2] / 2
  const cy = centre[1] + centre[3] / 2
  const w = rect[2] * (stored[0] as number)
  const h = rect[3] * (stored[1] as number)
  return (
    <div
      data-mark-id={mark.id}
      data-kind="textbox"
      data-color={key}
      style={{
        left: px(cx - w / 2),
        top: px(cy - h / 2),
        width: px(w),
        height: px(h),
        fontSize: px((fs ?? 0.018) * (stored[1] as number)),
        transform: view.rotation ? `rotate(${view.rotation}deg)` : undefined,
      }}
      className={cn(
        'absolute overflow-hidden rounded-sm border border-dashed bg-transparent leading-tight break-words whitespace-pre-wrap',
        INK_TEXT[key],
        INK_BORDER[key],
        onSelect && 'pointer-events-auto cursor-pointer',
        pulsing && 'mark-pulse',
      )}
    >
      {onSelect ? (
        <button
          type="button"
          tabIndex={-1}
          aria-label={describeMark(mark, legend)}
          onClick={() => onSelect(mark.id)}
          className="absolute inset-0 cursor-pointer text-left outline-none"
        >
          <span className="block p-0.5">{mark.comment}</span>
        </button>
      ) : (
        <span className="block p-0.5">{mark.comment}</span>
      )}
    </div>
  )
}

function PinMark({
  mark,
  view,
  legend,
  pulsing,
  onSelect,
}: {
  mark: MarkRecord
  view: Viewport
  legend: Legend
  pulsing: boolean
  onSelect?: (id: string) => void
}) {
  const key = markupOf(mark.color)
  const [x, y] = toViewportPoint((mark.geometry as { pt: [number, number] }).pt, view)
  return (
    <span
      data-mark-id={mark.id}
      data-kind="sticky"
      data-color={key}
      style={{ left: px(x) - 22, top: px(y) - 22 }}
      className="absolute grid size-11 place-items-center"
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={describeMark(mark, legend)}
        onClick={() => onSelect?.(mark.id)}
        className={cn(
          'pointer-events-auto grid size-11 place-items-center rounded-full outline-none',
          !onSelect && 'pointer-events-none',
        )}
      >
        <span
          className={cn(
            'grid size-7 place-items-center rounded-lg border-2 shadow-soft',
            HL_SOLID[key],
            HL_BORDER[key],
            'text-swatch-marker',
            pulsing && 'mark-pulse',
          )}
        >
          <StickyNote aria-hidden className="size-4" />
        </span>
      </button>
    </span>
  )
}

function FlagMark({
  mark,
  view,
  legend,
  pulsing,
  onSelect,
}: {
  mark: MarkRecord
  view: Viewport
  legend: Legend
  pulsing: boolean
  onSelect?: (id: string) => void
}) {
  const [x, y] = toViewportPoint([0, (mark.geometry as { y: number }).y], view)
  return (
    <span
      data-mark-id={mark.id}
      data-kind="bookmark"
      style={{ left: px(x), top: px(y) - 22 }}
      className="absolute grid h-11 w-9 place-items-center"
    >
      <button
        type="button"
        tabIndex={-1}
        aria-label={describeMark(mark, legend)}
        onClick={() => onSelect?.(mark.id)}
        className={cn(
          'pointer-events-auto grid h-11 w-9 place-items-center outline-none',
          !onSelect && 'pointer-events-none',
        )}
      >
        <span
          className={cn(
            'grid h-7 w-6 place-items-center rounded-r-md border-2 border-l-0 border-primary bg-primary text-primary-foreground shadow-soft',
            pulsing && 'mark-pulse',
          )}
        >
          <Bookmark aria-hidden className="size-4" />
        </span>
      </button>
    </span>
  )
}

/** A dashed frame around the selected mark (a frame, not a colour, so selection reads without seeing colour). */
function Outline({ mark, view }: { mark: MarkRecord; view: Viewport }) {
  const bbox = geometryBbox(mark.kind, mark.geometry)
  let box: Rect
  if (mark.kind === 'sticky') {
    const [x, y] = toViewportPoint([bbox[0], bbox[1]], view)
    box = [x - 18, y - 18, 36, 36]
  } else if (mark.kind === 'bookmark') {
    const [x, y] = toViewportPoint([0, bbox[1]], view)
    box = [x, y - 18, 30, 36]
  } else {
    box = toViewportRect(bbox, view)
  }
  const pad = 4
  return (
    <span
      data-selected-outline={mark.id}
      style={{
        left: px(box[0]) - pad,
        top: px(box[1]) - pad,
        width: px(box[2]) + pad * 2,
        height: px(box[3]) + pad * 2,
      }}
      className="absolute rounded-md border-2 border-dashed border-primary"
    />
  )
}
