import { Link, useRouterState } from '@tanstack/react-router'

import { useAuth } from '~/modules/auth'
import { useKeepAwake } from '~/modules/keepawake'
import { useFeatureFlag } from '~/modules/observability'
import { nowMs, useStopwatch, useStopwatchLive } from '~/modules/tracker'

import { MiniTimerView } from '../components/MiniTimerView'
import { useTimerTitle } from '../hooks/useDocumentTitle'
import { useFocusTimer } from '../hooks/useFocusTimer'
import { usePopOut } from '../hooks/usePopOut'
import { usePopoutSync } from '../hooks/usePopoutSync'
import { MINI_PATH } from '../lib/mini-window'
import { type PopoutControlId, popoutView } from '../lib/popout'
import { PopOutButton } from './PopOutButton'
import { PopOutFocus } from './PopOutFocus'
import { PopOutStopwatch } from './PopOutStopwatch'
import { PopOutWindow } from './PopOutWindow'

const linkClass = 'outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40'

/**
 * A running (or paused) Pomodoro round or break. It also closes phases and plays the alerts while the student is
 * elsewhere, and it owns the one timer the floating window draws, so the window needs no timer of its own.
 */
function FocusMini({ ownTitle }: { ownTitle: boolean }) {
  const f = useFocusTimer()
  const pop = usePopOut()
  const stopwatchRuns = useStopwatchLive()
  const t = f.timer
  useTimerTitle(t, document.title || 'Artha', f.remaining, ownTitle)

  const popped = pop.isOpen && !stopwatchRuns && !f.featureDisabled
  usePopoutSync(t, !!t && f.remaining === 0)
  // While the window is out, the screen is held from its document: the tab's own lock is released once it is hidden.
  useKeepAwake(
    popped && t ? { running: t.status === 'running', focus: t.phase === 'focus' } : null,
    f.settings,
    pop.window,
  )

  const view = popoutView(t, f.idle, null, nowMs(), null)
  const onControl = (id: PopoutControlId) => (id === 'resume' ? f.resume() : id === 'pause' ? f.pause() : undefined)
  return (
    <>
      {f.featureDisabled || !t ? null : (
        <MiniTimerView
          variant="corner"
          view={view}
          controls={view.controls}
          busy={f.busy}
          onControl={onControl}
          renderLink={(children) => (
            <Link to="/app/focus" className={`flex items-center gap-2 ${linkClass}`}>
              {children}
            </Link>
          )}
          action={<PopOutButton source="mini" timer="focus" size={f.settings?.popout_size} />}
        />
      )}
      {popped ? (
        <PopOutWindow>
          <PopOutFocus f={f} />
        </PopOutWindow>
      ) : null}
    </>
  )
}

function StopwatchMini() {
  const pop = usePopOut()
  const sw = useStopwatch({ timers: pop.window })
  const running = sw.stopwatch
  useKeepAwake(
    pop.isOpen && running ? { running: running.status === 'running' && !running.idle_pending, focus: true } : null,
    undefined,
    pop.window,
  )
  if (sw.featureDisabled || !running) return null
  const view = popoutView(null, null, { paused: running.status === 'paused', seconds: sw.seconds }, nowMs(), null)
  return (
    <>
      <MiniTimerView
        variant="corner"
        view={view}
        controls={view.controls}
        busy={sw.busy}
        onControl={(id) => sw.toggle.mutate(id === 'resume' ? 'resume' : 'pause')}
        renderLink={(children) => (
          <Link to="/app/tracker" className={`flex items-center gap-2 ${linkClass}`}>
            {children}
          </Link>
        )}
        action={<PopOutButton source="mini" timer="stopwatch" />}
      />
      {pop.isOpen ? (
        <PopOutWindow>
          <PopOutStopwatch sw={sw} />
        </PopOutWindow>
      ) : null}
    </>
  )
}

/**
 * Shown on every page once a student is signed in. Whichever timer is running stays in the corner (only one can),
 * including on the focus and tracker screens, and either one can be popped out into the floating window. Each timer
 * still follows its own feature flag.
 */
export function LiveMiniTimer() {
  const { user, loading } = useAuth()
  const path = useRouterState({ select: (s) => s.location.pathname })
  const focusOn = useFeatureFlag('focus_timer')
  const trackerOn = useFeatureFlag('time_tracker')
  // The fallback window is its own timer page: the corner timer would be a second one in the same window.
  if (loading || !user || path === MINI_PATH) return null
  return (
    <>
      {focusOn ? <FocusMini ownTitle={!path.startsWith('/app/focus')} /> : null}
      {trackerOn ? <StopwatchMini /> : null}
    </>
  )
}
