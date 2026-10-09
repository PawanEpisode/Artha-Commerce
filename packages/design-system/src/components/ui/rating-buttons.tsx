import * as React from 'react'

import { cn } from '../../lib/utils'
import { Kbd } from './kbd'

export type Rating = 1 | 2 | 3 | 4

/** The four answers of a review, in key order. The words and the keys are part of the product, not a theme choice. */
export const RATINGS: ReadonlyArray<{ rating: Rating; label: string; key: string; tone: string }> = [
  { rating: 1, label: 'Again', key: '1', tone: 'border-error-border bg-error-bg text-error-fg' },
  { rating: 2, label: 'Hard', key: '2', tone: 'border-warning-border bg-warning-bg text-warning-fg' },
  { rating: 3, label: 'Good', key: '3', tone: 'border-success-border bg-success-bg text-success-fg' },
  { rating: 4, label: 'Easy', key: '4', tone: 'border-info-border bg-info-bg text-info-fg' },
]

/** The rating a key press stands for ("1" to "4"), or null. */
export function ratingForKey(key: string): Rating | null {
  const found = RATINGS.find((r) => r.key === key)
  return found ? found.rating : null
}

/**
 * Roving focus over `count` buttons in a row: arrows move one step and stop at the ends (no wrap, so Left on "Again" stays on
 * "Again"), Home and End jump. Returns the new index, or null when the key does nothing.
 */
export function rovingIndex(current: number, key: string, count: number): number | null {
  if (count <= 0) return null
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      return Math.min(current + 1, count - 1)
    case 'ArrowLeft':
    case 'ArrowUp':
      return Math.max(current - 1, 0)
    case 'Home':
      return 0
    case 'End':
      return count - 1
    default:
      return null
  }
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

interface RatingButtonsProps extends Omit<React.ComponentProps<'div'>, 'onChange'> {
  onRate: (rating: Rating) => void
  /** What each answer would schedule ("10 min", "5 d"), from the scheduler's preview. Shown under the word. */
  previews?: Partial<Record<Rating, string>>
  disabled?: boolean
  /** Show the key under each button ("1" to "4"). On by default; hide it on touch layouts. */
  showKeys?: boolean
  /** Also answer to the keys 1 to 4 anywhere on the page (not while typing in a field). The review screen turns this on. */
  shortcuts?: boolean
  /** Accessible name of the group. */
  label?: string
}

/**
 * Four equal buttons: Again, Hard, Good, Easy, each with the next interval and its key. The row is one tab stop with
 * arrow-key movement (roving focus); Enter or Space presses the focused one, and 1 to 4 press directly. The meaning is the
 * word, never the colour. Every target is at least 44 px.
 */
export function RatingButtons({
  onRate,
  previews,
  disabled = false,
  showKeys = true,
  shortcuts = false,
  label = 'How well did you remember it?',
  className,
  ...props
}: RatingButtonsProps) {
  const refs = React.useRef<Array<HTMLButtonElement | null>>([])
  const [active, setActive] = React.useState(2) // "Good" is the usual answer, so it is the one Tab lands on

  React.useEffect(() => {
    if (!shortcuts || disabled) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || isTyping(e.target)) return
      const rating = ratingForKey(e.key)
      if (rating) onRate(rating)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [shortcuts, disabled, onRate])

  const onKeyDown = (e: React.KeyboardEvent, index: number) => {
    const next = rovingIndex(index, e.key, RATINGS.length)
    if (next === null) return
    e.preventDefault()
    setActive(next)
    refs.current[next]?.focus()
  }

  return (
    <div
      data-slot="rating-buttons"
      role="group"
      aria-label={label}
      className={cn('grid grid-cols-4 gap-2', className)}
      {...props}
    >
      {RATINGS.map((r, i) => {
        const preview = previews?.[r.rating]
        return (
          <button
            key={r.rating}
            ref={(el) => {
              refs.current[i] = el
            }}
            type="button"
            disabled={disabled}
            tabIndex={i === active ? 0 : -1}
            aria-keyshortcuts={r.key}
            aria-label={preview ? `${r.label}, next in ${preview}` : r.label}
            onFocus={() => setActive(i)}
            onKeyDown={(e) => onKeyDown(e, i)}
            onClick={() => onRate(r.rating)}
            className={cn(
              'flex min-h-14 min-w-11 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-xl border px-1 py-2 text-sm font-semibold transition-shadow outline-none focus-visible:ring-[3px] focus-visible:ring-ring/60 enabled:active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none motion-reduce:active:scale-100',
              r.tone,
            )}
          >
            <span className="text-base">{r.label}</span>
            {preview ? (
              <span aria-hidden className="text-xs font-medium tabular-nums">
                {preview}
              </span>
            ) : null}
            {showKeys ? (
              <Kbd aria-hidden className="hidden sm:inline-flex">
                {r.key}
              </Kbd>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}
