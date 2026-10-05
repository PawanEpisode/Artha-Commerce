import { ProgressRing } from '@artha/design-system'

import { formatRemaining, PHASE_LABEL, spokenRemaining } from '../lib/timer-math'
import type { Phase, TimerStatus } from '../lib/types'

interface Props {
  phase: Phase | null
  status: TimerStatus | null
  remainingSeconds: number
  percent: number
  /** "Round 2 of 4" or the idle prompt. */
  caption: string
  size?: number
}

/**
 * The big countdown. The ring is decoration plus a progress role; the time itself is a `timer` with a spoken label.
 * The label changes only once a minute so a screen reader is not interrupted every second.
 */
export function TimerRing({ phase, status, remainingSeconds, percent, caption, size = 280 }: Props) {
  const minuteLabel = spokenRemaining(Math.ceil(remainingSeconds / 60) * 60)
  return (
    <ProgressRing
      value={percent}
      size={size}
      strokeWidth={14}
      label={phase ? `${PHASE_LABEL[phase]} progress` : 'Timer progress'}
      className="mx-auto"
    >
      <span className="flex flex-col items-center gap-1">
        <span className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
          {phase ? PHASE_LABEL[phase] : 'Ready'}
          {status === 'paused' ? ' · paused' : ''}
        </span>
        <span
          role="timer"
          aria-label={`${phase ? PHASE_LABEL[phase] : 'Timer'}: about ${minuteLabel} left`}
          className="font-display text-6xl font-extrabold tracking-tight tabular-nums"
        >
          <span aria-hidden>{formatRemaining(remainingSeconds)}</span>
        </span>
        <span className="text-sm text-muted-foreground">{caption}</span>
      </span>
    </ProgressRing>
  )
}
