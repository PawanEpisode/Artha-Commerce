import { Link, useRouterState } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'
import { useFeatureFlag } from '~/modules/observability'
import { formatClock, spokenDuration, useStopwatch } from '~/modules/tracker'

import { MiniTimerView } from '../components/MiniTimerView'
import { useTimerTitle } from '../hooks/useDocumentTitle'
import { useFocusTimer } from '../hooks/useFocusTimer'
import { formatRemaining, PHASE_LABEL, spokenRemaining } from '../lib/timer-math'

const linkClass = 'outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40'

/** A running (or paused) Pomodoro round or break. It also closes phases and plays the alerts while the student is elsewhere. */
function FocusMini({ ownTitle }: { ownTitle: boolean }) {
  const f = useFocusTimer()
  const t = f.timer
  useTimerTitle(t, document.title || 'Artha', f.remaining, ownTitle)
  if (f.featureDisabled || !t) return null
  const away = t.status === 'away'
  return (
    <MiniTimerView
      label={t.phase === 'focus' ? 'Focus round' : PHASE_LABEL[t.phase]}
      phase={t.phase}
      paused={t.status === 'paused'}
      clock={away ? 'Done?' : formatRemaining(f.remaining)}
      spoken={away ? 'The round ended while you were away' : `${spokenRemaining(f.remaining)} left`}
      busy={f.busy}
      onPause={t.phase === 'focus' && !away ? f.pause : undefined}
      onResume={t.phase === 'focus' && !away ? f.resume : undefined}
      renderLink={(children) => (
        <Link to="/app/focus" className={`flex items-center gap-2 ${linkClass}`}>
          {children}
        </Link>
      )}
    />
  )
}

function StopwatchMini() {
  const sw = useStopwatch()
  if (sw.featureDisabled || !sw.stopwatch) return null
  return (
    <MiniTimerView
      label="Stopwatch"
      phase="stopwatch"
      paused={sw.stopwatch.status === 'paused'}
      clock={formatClock(sw.seconds)}
      spoken={`Elapsed ${spokenDuration(sw.seconds)}`}
      busy={sw.busy}
      onPause={() => sw.toggle.mutate('pause')}
      onResume={() => sw.toggle.mutate('resume')}
      renderLink={(children) => (
        <Link to="/app/tracker" className={`flex items-center gap-2 ${linkClass}`}>
          {children}
        </Link>
      )}
    />
  )
}

/**
 * Shown on every page once a student is signed in. Whichever timer is running stays in the corner (only one can),
 * including on the focus and tracker screens. Each timer still follows its own feature flag.
 */
export function LiveMiniTimer() {
  const { user, loading } = useAuth()
  const path = useRouterState({ select: (s) => s.location.pathname })
  const focusOn = useFeatureFlag('focus_timer')
  const trackerOn = useFeatureFlag('time_tracker')
  if (loading || !user) return null
  return (
    <>
      {focusOn ? <FocusMini ownTitle={!path.startsWith('/app/focus')} /> : null}
      {trackerOn ? <StopwatchMini /> : null}
    </>
  )
}
