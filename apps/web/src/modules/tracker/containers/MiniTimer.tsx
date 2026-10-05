import { Button, Pause, Play, Timer } from '@artha/design-system'
import { Link, useRouterState } from '@tanstack/react-router'

import { useFeatureFlag } from '~/modules/observability'

import { useStopwatch } from '../hooks/useStopwatch'
import { formatClock, spokenDuration } from '../lib/duration'

/**
 * A small stopwatch pinned to the corner of every signed-in screen while one is running, so the student can pause
 * or find it from anywhere. Renders nothing when the flag is off, no stopwatch runs, or the full tracker is open.
 * `useLiveTimer` is the seam for the Pomodoro timer (F-01.1): it will report its own running round the same way.
 */
export function useLiveTimer() {
  const timer = useStopwatch()
  return {
    kind: timer.stopwatch ? ('stopwatch' as const) : null,
    status: timer.stopwatch?.status ?? null,
    seconds: timer.seconds,
    pause: () => timer.toggle.mutate('pause'),
    resume: () => timer.toggle.mutate('resume'),
    busy: timer.busy,
    featureDisabled: timer.featureDisabled,
  }
}

function Mini() {
  const t = useLiveTimer()
  const path = useRouterState({ select: (s) => s.location.pathname })
  if (t.featureDisabled || !t.kind || path.startsWith('/app/tracker')) return null
  return (
    <div
      role="region"
      aria-label="Running stopwatch"
      className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-2xl border border-border bg-popover p-2 pl-4 shadow-(--shadow-lift)"
    >
      <Timer className="size-4 text-primary" aria-hidden />
      <Link
        to="/app/tracker"
        className="font-display font-bold tabular-nums outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
      >
        <span className="sr-only">Open the time tracker. Elapsed {spokenDuration(t.seconds)}. </span>
        <span aria-hidden>{formatClock(t.seconds)}</span>
      </Link>
      {t.status === 'running' ? (
        <Button size="icon" variant="outline" aria-label="Pause stopwatch" onClick={t.pause} disabled={t.busy}>
          <Pause aria-hidden />
        </Button>
      ) : (
        <Button size="icon" aria-label="Resume stopwatch" onClick={t.resume} disabled={t.busy}>
          <Play aria-hidden />
        </Button>
      )}
    </div>
  )
}

/** Mounted once in the signed-in layout. Gated by the `time_tracker` flag. */
export function MiniTimer() {
  const enabled = useFeatureFlag('time_tracker')
  return enabled ? <Mini /> : null
}
