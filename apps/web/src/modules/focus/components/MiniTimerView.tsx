import { Button, Coffee, Pause, Play, Timer } from '@artha/design-system'
import type { ReactNode } from 'react'

import { formatRemaining, PHASE_LABEL, spokenRemaining } from '../lib/timer-math'
import type { Phase } from '../lib/types'

interface Props {
  /** The running kind, for the label: "Focus", "Break", "Stopwatch". */
  label: string
  phase: Phase | 'stopwatch'
  paused: boolean
  /** Text of the clock, already formatted. */
  clock: string
  spoken: string
  busy: boolean
  onPause?: () => void
  onResume?: () => void
  /** The link wrapping the clock, so the container owns routing. */
  renderLink: (children: ReactNode) => ReactNode
}

/** The small corner timer shown on every signed-in screen while a round, break or stopwatch runs. */
export function MiniTimerView(p: Props) {
  const isBreak = p.phase === 'short_break' || p.phase === 'long_break'
  const Icon = isBreak ? Coffee : Timer
  return (
    <div
      role="region"
      aria-label={`Running ${p.label.toLowerCase()}`}
      className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-2xl border border-border bg-popover p-2 pl-4 shadow-(--shadow-lift)"
    >
      <Icon className="size-4 text-primary" aria-hidden />
      {p.renderLink(
        <>
          <span className="sr-only">
            Open the {p.label.toLowerCase()}. {p.spoken}.{' '}
          </span>
          <span aria-hidden className="font-display font-bold tabular-nums">
            {p.clock}
          </span>
        </>,
      )}
      {p.onPause && p.onResume ? (
        p.paused ? (
          <Button size="icon" aria-label={`Resume ${p.label.toLowerCase()}`} onClick={p.onResume} disabled={p.busy}>
            <Play aria-hidden />
          </Button>
        ) : (
          <Button
            size="icon"
            variant="outline"
            aria-label={`Pause ${p.label.toLowerCase()}`}
            onClick={p.onPause}
            disabled={p.busy}
          >
            <Pause aria-hidden />
          </Button>
        )
      ) : null}
    </div>
  )
}

export { formatRemaining, PHASE_LABEL, spokenRemaining }
