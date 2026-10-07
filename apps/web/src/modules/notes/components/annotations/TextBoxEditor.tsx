import { Button, cn, Trash2 } from '@artha/design-system'
import { type KeyboardEvent, type PointerEvent as ReactPointerEvent, useEffect, useRef, useState } from 'react'

import type { InkColor } from '../../lib/annotation-types'
import { MAX_FONT, MIN_FONT, type Rect } from '../../lib/geometry'
import { clampFontSize, MAX_COMMENT, moveRect, resizeRect } from '../../lib/mark-drafts'
import { INK_BORDER, INK_TEXT } from './mark-styles'

export interface TextBoxEditorProps {
  /** Page box on screen, CSS pixels. The editor works in the unrotated view (a rotated page edits in the sheet). */
  width: number
  height: number
  rect: Rect
  /** Font size as a fraction of the page height. */
  fs: number
  text: string
  color: InkColor
  onTextChange: (text: string) => void
  onRectChange: (rect: Rect) => void
  onFontSizeChange: (fs: number) => void
  onDone: () => void
  onDelete: () => void
}

const STEP = 0.01
const BIG_STEP = 0.05

/**
 * Edits a text box in place on the page: type in it, drag the grip to move it, drag the corner to resize it, A- and A+ for
 * the size (within the allowed range). The grips are also buttons: arrow keys move or resize by 1% (5% with Shift), so
 * nothing needs a pointer. Plain text, 2,000 characters at most.
 */
export function TextBoxEditor({
  width,
  height,
  rect,
  fs,
  text,
  color,
  onTextChange,
  onRectChange,
  onFontSizeChange,
  onDone,
  onDelete,
}: TextBoxEditorProps) {
  const field = useRef<HTMLTextAreaElement>(null)
  const drag = useRef<{ mode: 'move' | 'size'; x: number; y: number; rect: Rect } | null>(null)
  const [live, setLive] = useState<Rect | null>(null)
  const shown = live ?? rect

  useEffect(() => {
    field.current?.focus()
  }, [])

  const begin = (mode: 'move' | 'size') => (e: ReactPointerEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    e.currentTarget.setPointerCapture?.(e.pointerId)
    drag.current = { mode, x: e.clientX, y: e.clientY, rect }
  }
  const moveDrag = (e: ReactPointerEvent<HTMLButtonElement>) => {
    const d = drag.current
    if (!d) return
    const dx = (e.clientX - d.x) / width
    const dy = (e.clientY - d.y) / height
    setLive(d.mode === 'move' ? moveRect(d.rect, dx, dy) : resizeRect(d.rect, dx, dy))
  }
  const endDrag = () => {
    if (drag.current && live) onRectChange(live)
    drag.current = null
    setLive(null)
  }

  const keys = (mode: 'move' | 'size') => (e: KeyboardEvent<HTMLButtonElement>) => {
    const step = e.shiftKey ? BIG_STEP : STEP
    const delta: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    }
    const d = delta[e.key]
    if (!d) return
    e.preventDefault()
    onRectChange(mode === 'move' ? moveRect(rect, d[0], d[1]) : resizeRect(rect, d[0], d[1]))
  }

  const box = { left: shown[0] * width, top: shown[1] * height, width: shown[2] * width, height: shown[3] * height }
  return (
    <div data-slot="textbox-editor" style={box} className="pointer-events-auto absolute z-20">
      <textarea
        ref={field}
        value={text}
        maxLength={MAX_COMMENT}
        aria-label="Text box content"
        onChange={(e) => onTextChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.stopPropagation()
            onDone()
          }
        }}
        style={{ fontSize: fs * height }}
        className={cn(
          'size-full resize-none rounded-sm border-2 border-dashed bg-card/80 p-0.5 leading-tight outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60',
          INK_TEXT[color],
          INK_BORDER[color],
        )}
      />
      <button
        type="button"
        aria-label="Move text box. Drag, or use the arrow keys."
        onPointerDown={begin('move')}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onKeyDown={keys('move')}
        className="absolute -top-11 left-0 grid size-11 cursor-move place-items-center rounded-lg border border-border bg-card text-xs font-semibold shadow-soft outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60"
        style={{ touchAction: 'none' }}
      >
        Move
      </button>
      <button
        type="button"
        aria-label="Resize text box. Drag, or use the arrow keys."
        onPointerDown={begin('size')}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onKeyDown={keys('size')}
        className="absolute -right-5 -bottom-5 grid size-11 cursor-nwse-resize place-items-center rounded-lg border border-border bg-card text-xs font-semibold shadow-soft outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60"
        style={{ touchAction: 'none' }}
      >
        Size
      </button>
      <div className="absolute -top-11 right-0 flex items-center gap-1 rounded-lg border border-border bg-card p-0.5 shadow-soft">
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          aria-label="Smaller text"
          disabled={fs <= MIN_FONT}
          onClick={() => onFontSizeChange(clampFontSize(fs - 0.002))}
        >
          A-
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-11"
          aria-label="Larger text"
          disabled={fs >= MAX_FONT}
          onClick={() => onFontSizeChange(clampFontSize(fs + 0.002))}
        >
          A+
        </Button>
        <Button variant="ghost" size="icon" className="size-11" aria-label="Delete text box" onClick={onDelete}>
          <Trash2 aria-hidden />
        </Button>
        <Button size="sm" className="min-h-11" onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  )
}
