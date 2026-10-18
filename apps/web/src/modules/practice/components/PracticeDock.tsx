import { Clock, cn, Pause, TriangleAlert } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { PracticeClock } from '../lib/clock'

export interface PracticeDockProps {
  clock: Exclude<PracticeClock, { kind: 'waiting' }>
  /** The clock as text ("12:04"). */
  time: string
  /** What the session is, e.g. "Timed practice". Names the region for screen readers. */
  title: string
  /** Lift the dock above another corner timer. */
  raised: boolean
  /** Screen-reader text for the last threshold crossed ("5 minutes left."). Rendered in a polite live region. */
  announcement: string
  /** Wraps the clock so the container owns routing. */
  renderLink: (children: ReactNode) => ReactNode
}

const LOW = 60 // seconds: the clock turns to the danger colour and the icon changes

/**
 * The practice timer docked in the corner of every page while a session runs, like the focus timer: time left for a
 * timed session, time spent for an untimed one. Colour is never the only signal: the icon, the word and the screen
 * reader text change as well. Props only.
 */
export function PracticeDock({ clock, time, title, raised, announcement, renderLink }: PracticeDockProps) {
  const countdown = clock.kind === 'countdown'
  const expired = countdown && clock.expired
  const low = countdown && !clock.paused && !expired && clock.seconds <= LOW
  const Icon = clock.paused ? Pause : low || expired ? TriangleAlert : Clock
  const word = expired ? "Time's up" : clock.paused ? 'Paused' : countdown ? 'left' : 'spent'

  return (
    <div
      role="region"
      aria-label={`${title} timer`}
      className={cn(
        'fixed right-4 z-40 flex items-center gap-2 rounded-2xl border border-border bg-popover px-4 py-2 shadow-(--shadow-lift)',
        raised ? 'bottom-20' : 'bottom-4',
      )}
    >
      {renderLink(
        <span className="flex items-center gap-2">
          <Icon
            aria-hidden
            className={cn(
              'size-4',
              low || expired ? 'text-destructive' : 'text-primary',
              low && 'motion-safe:animate-pulse',
            )}
          />
          <span className="sr-only">
            {title}. {expired ? "Time's up" : clock.paused ? 'Paused' : countdown ? 'Time left' : 'Time spent'}. Open
            the session.
          </span>
          <span
            aria-hidden
            className={cn('font-display font-bold tabular-nums', (low || expired) && 'text-destructive')}
          >
            {time}
          </span>
          <span aria-hidden className="text-xs text-muted-foreground">
            {word}
          </span>
        </span>,
      )}
      <span className="sr-only" role="status" aria-live="polite">
        {announcement}
      </span>
    </div>
  )
}
