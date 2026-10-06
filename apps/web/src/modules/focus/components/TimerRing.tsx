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
}

/**
 * The big countdown, centred. The ring is decoration plus a progress role; the time itself is a `timer` with a spoken
 * label. The label changes only once a minute so a screen reader is not interrupted every second.
 */
export function TimerRing({ phase, status, remainingSeconds, overtimeSeconds = null, percent, caption }: Props) {
  const extra = overtimeSeconds !== null
  const minuteLabel = spokenRemaining(Math.ceil((extra ? overtimeSeconds : remainingSeconds) / 60) * 60)
  const running = status === 'running'
  const size = useRingSize()
  return (
    <div className="flex w-full justify-center">
      <div className="relative">
        {running ? (
          <span
            aria-hidden
            className="absolute -inset-3 rounded-full bg-primary/10 motion-safe:animate-pulse motion-reduce:bg-primary/5"
          />
        ) : null}
        <ProgressRing
          value={extra ? 100 : percent}
          size={size}
          strokeWidth={14}
          label={phase ? `${PHASE_LABEL[phase]} progress` : 'Timer progress'}
          className="relative"
        >
          <span className="flex max-w-full flex-col items-center gap-1 px-4 text-center">
            <span className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
              {extra ? 'Extra focus' : phase ? PHASE_LABEL[phase] : 'Ready'}
              {status === 'paused' ? ' · paused' : ''}
            </span>
            <span
              key={status ? 'live' : String(remainingSeconds)}
              role="timer"
              aria-label={
                extra
                  ? `Extra focus: about ${minuteLabel} past the round`
                  : `${phase ? PHASE_LABEL[phase] : 'Timer'}: about ${minuteLabel} left`
              }
              className="font-display text-5xl font-extrabold tracking-tight tabular-nums motion-safe:animate-in motion-safe:fade-in-0 motion-reduce:animate-none sm:text-6xl"
            >
              <span aria-hidden>{extra ? formatOvertime(overtimeSeconds) : formatRemaining(remainingSeconds)}</span>
            </span>
            <span className="text-sm text-muted-foreground">{caption}</span>
          </span>
        </ProgressRing>
      </div>
    </div>
  )
}

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
