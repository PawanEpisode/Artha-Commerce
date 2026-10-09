import * as React from 'react'

import { cn } from '../../lib/utils'
import { Button } from './button'
import { Kbd } from './kbd'

export type SwipeDirection = 'left' | 'right'

/**
 * The swipe a pointer movement makes: mostly horizontal and at least `threshold` pixels. Anything else (a scroll, a tap, a
 * diagonal drag) is not a swipe. Left means Again and right means Good on the review screen, set by the caller.
 */
export function swipeDirection(dx: number, dy: number, threshold = 64): SwipeDirection | null {
  if (Math.abs(dx) < threshold || Math.abs(dx) < Math.abs(dy) * 1.5) return null
  return dx < 0 ? 'left' : 'right'
}

interface FlipCardProps extends Omit<React.ComponentProps<'div'>, 'children'> {
  front: React.ReactNode
  back: React.ReactNode
  flipped: boolean
  /** Called by the "Show answer" button. The card never flips itself, so the caller owns the state (keys, undo). */
  onFlip?: () => void
  /** Swipes on the card, only while `flipped` and `swipeEnabled`. A button alternative must exist (the rating buttons). */
  onSwipe?: (direction: SwipeDirection) => void
  swipeEnabled?: boolean
  /** Accessible name of the card, e.g. "Card 3 of 20". */
  label?: string
  flipLabel?: string
  /** Show the Show answer button under the card (on by default). Turn it off when the caller supplies its own. */
  showFlipButton?: boolean
  /** Move focus to the answer whenever the card turns, whatever turned it (a key, a gesture, the caller's own button). */
  focusOnFlip?: boolean
}

/**
 * A flashcard: a front, a back, and a button that turns it over. With motion it turns in 300 ms; with reduced motion the
 * change is instant (a 0 ms crossfade), never a movement. The hidden face is `inert` and `aria-hidden`; the change is announced
 * ("Answer shown") and focus moves to the answer so a keyboard or screen-reader user continues from there.
 */
export function FlipCard({
  front,
  back,
  flipped,
  onFlip,
  onSwipe,
  swipeEnabled = false,
  label = 'Flashcard',
  flipLabel = 'Show answer',
  showFlipButton = true,
  focusOnFlip = false,
  className,
  ...props
}: FlipCardProps) {
  const buttonRef = React.useRef<HTMLButtonElement>(null)
  const backRef = React.useRef<HTMLDivElement>(null)
  const start = React.useRef<{ x: number; y: number } | null>(null)
  const turnedByButton = React.useRef(false)
  const wasFlipped = React.useRef(flipped)

  React.useEffect(() => {
    // Only when this card was turned by its own button (which leaves the page as the card turns): a new card keeps the caller's focus
    if (flipped && (turnedByButton.current || (focusOnFlip && !wasFlipped.current))) backRef.current?.focus()
    wasFlipped.current = flipped
    turnedByButton.current = false
  }, [flipped, focusOnFlip])

  const onPointerDown = (e: React.PointerEvent) => {
    start.current = swipeEnabled && flipped ? { x: e.clientX, y: e.clientY } : null
  }
  const onPointerUp = (e: React.PointerEvent) => {
    const s = start.current
    start.current = null
    if (!s || !onSwipe) return
    const dir = swipeDirection(e.clientX - s.x, e.clientY - s.y)
    if (dir) onSwipe(dir)
  }

  return (
    <div data-slot="flip-card" className={cn('grid gap-3', className)} {...props}>
      <div
        role="group"
        aria-roledescription="flashcard"
        aria-label={label}
        data-flipped={flipped}
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={() => (start.current = null)}
        className="relative grid touch-pan-y [perspective:1200px]"
      >
        <div
          className={cn(
            'col-start-1 row-start-1 grid [transform-style:preserve-3d] motion-safe:transition-transform motion-safe:duration-300 motion-reduce:transition-none',
            flipped && 'motion-safe:[transform:rotateY(180deg)]',
          )}
        >
          <Face hidden={flipped} className="motion-reduce:data-[hidden=true]:hidden">
            {front}
          </Face>
          <Face
            ref={backRef}
            hidden={!flipped}
            back
            tabIndex={flipped ? -1 : undefined}
            className="motion-reduce:data-[hidden=true]:hidden"
          >
            {back}
          </Face>
        </div>
      </div>
      <p role="status" aria-live="polite" className="sr-only">
        {flipped ? 'Answer shown' : 'Question shown'}
      </p>
      {showFlipButton && !flipped ? (
        <Button
          ref={buttonRef}
          type="button"
          size="lg"
          className="w-full"
          aria-keyshortcuts="Space Enter"
          onClick={() => {
            turnedByButton.current = true
            onFlip?.()
          }}
        >
          {flipLabel}
          <Kbd aria-hidden className="ml-2 hidden sm:inline-flex">
            Space
          </Kbd>
        </Button>
      ) : null}
    </div>
  )
}

interface FaceProps extends React.ComponentProps<'div'> {
  hidden: boolean
  back?: boolean
}

function Face({ hidden, back = false, className, children, ...props }: FaceProps) {
  return (
    <div
      data-hidden={hidden}
      aria-hidden={hidden || undefined}
      inert={hidden}
      className={cn(
        'col-start-1 row-start-1 grid min-h-48 content-center gap-3 rounded-2xl border border-border bg-card p-5 text-center shadow-soft outline-none [backface-visibility:hidden] focus-visible:ring-[3px] focus-visible:ring-ring/40 sm:p-8',
        back && 'motion-safe:[transform:rotateY(180deg)]',
        hidden && 'pointer-events-none',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
