import { ProgressRing } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { formatOvertime, formatRemaining, PHASE_LABEL, spokenRemaining } from '../lib/timer-math'
import type { Phase, TimerStatus } from '../lib/types'

interface Props {
  phase: Phase | null
  status: TimerStatus | null
  remainingSeconds: number
  /** Extra focus time past the planned length. When set the ring is full and the clock counts up. */
  overtimeSeconds?: number | null
  percent: number
  /** "Round 2 of 4" or the idle prompt. */
  caption: string
  /** The small ring of the floating window: fixed size, smaller type, one short label. */
  compact?: boolean
  /** The phase just ended: text takes the success tone so it stays readable on the phase-end tint. */
  ended?: boolean
  /** What a screen reader says for the clock (the floating window gives the exact time); default is the minute. */
  spoken?: string
  /** The clock text and the small label above it, when the caller has already worded them (the floating window). */
  clock?: string
  label?: string
}

/**
 * The big countdown, centred. The ring is decoration plus a progress role; the time itself is a `timer` with a spoken
 * label. The label changes only once a minute so a screen reader is not interrupted every second.
 */
export function TimerRing({
  phase,
  status,
  remainingSeconds,
  overtimeSeconds = null,
  percent,
  caption,
  compact = false,
  ended = false,
  spoken,
  clock,
  label,
}: Props) {
  const extra = overtimeSeconds !== null
  const minuteLabel = spokenRemaining(Math.ceil((extra ? overtimeSeconds : remainingSeconds) / 60) * 60)
  const running = status === 'running'
  const responsive = useRingSize()
  const size = compact ? COMPACT_RING : responsive
  const quiet = ended ? 'text-success-fg' : 'text-muted-foreground'
  const kind = label ?? (extra ? 'Extra focus' : phase ? PHASE_LABEL[phase] : 'Ready')
  return (
    <div className="flex w-full justify-center">
      <div className="relative">
        {running ? (
          <span
            aria-hidden
            className={`absolute rounded-full bg-primary/10 motion-safe:animate-pulse motion-reduce:bg-primary/5 ${compact ? '-inset-1.5' : '-inset-3'}`}
          />
        ) : null}
        <ProgressRing
          value={extra ? 100 : percent}
          size={size}
          strokeWidth={compact ? 10 : 14}
          label={phase ? `${PHASE_LABEL[phase]} progress` : 'Timer progress'}
          className="relative"
        >
          <span
            className={`flex max-w-full flex-col items-center text-center ${compact ? 'gap-0 px-2' : 'gap-1 px-4'}`}
          >
            <span className={`font-semibold tracking-wide uppercase ${quiet} ${compact ? 'text-xs' : 'text-sm'}`}>
              {kind}
              {!compact && !label && status === 'paused' ? ' · paused' : ''}
            </span>
            <span
              key={status ? 'live' : String(remainingSeconds)}
              role="timer"
              aria-label={
                spoken ??
                (extra
                  ? `Extra focus: about ${minuteLabel} past the round`
                  : `${phase ? PHASE_LABEL[phase] : 'Timer'}: about ${minuteLabel} left`)
              }
              className={`font-display font-extrabold tracking-tight tabular-nums ${ended ? 'text-success-fg' : ''} motion-safe:animate-in motion-safe:fade-in-0 motion-reduce:animate-none ${compact ? 'text-3xl' : 'text-5xl sm:text-6xl'}`}
            >
              <span aria-hidden>
                {clock ?? (extra ? formatOvertime(overtimeSeconds) : formatRemaining(remainingSeconds))}
              </span>
            </span>
            <span className={`${quiet} ${compact ? 'text-xs' : 'text-sm'}`}>{caption}</span>
          </span>
        </ProgressRing>
      </div>
    </div>
  )
}

/** The floating window's ring: with the 10px stroke it leaves room for a 30px clock inside a 320 x 300 window. */
const COMPACT_RING = 148

/** 220px fits a 320px screen once page and card padding are subtracted; wider screens get the full ring. */
function useRingSize() {
  const [size, setSize] = useState(220)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(min-width: 640px)')
    const apply = () => setSize(query.matches ? 280 : 220)
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [])
  return size
}
