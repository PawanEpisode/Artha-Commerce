import { Navigate } from '@tanstack/react-router'
import { type ReactNode, useEffect, useState } from 'react'

import { useFeatureFlag } from '~/modules/observability'
import { useStopwatch } from '~/modules/tracker'

import { MiniWindowNote } from '../components/MiniWindowNote'
import { useTimerTitle } from '../hooks/useDocumentTitle'
import { type FocusTimerApi, useFocusTimer } from '../hooks/useFocusTimer'
import { useMiniWindowPresence } from '../hooks/useMiniWindowPresence'
import { useWindowSize } from '../hooks/useWindowSize'
import { markMiniNoteSeen, miniLayout, miniNoteSeen } from '../lib/mini-window'
import { PopOutFocus, type WindowLayout } from './PopOutFocus'
import { PopOutStopwatch } from './PopOutStopwatch'

const TITLE = 'Artha timer'

/** The stopwatch when one runs, otherwise what the Pomodoro view says (only one timer can be live). */
function StopwatchOrFocus({ layout, focus }: { layout: WindowLayout; focus: ReactNode }) {
  const sw = useStopwatch()
  if (sw.featureDisabled || !sw.stopwatch) return focus
  return <PopOutStopwatch sw={sw} layout={layout} canGoBack={false} />
}

function MiniWindow() {
  const f: FocusTimerApi = useFocusTimer()
  const trackerOn = useFeatureFlag('time_tracker')
  const { width, height } = useWindowSize()
  const layout: WindowLayout = { size: miniLayout(width, height), fillParent: true }
  useMiniWindowPresence(f.timer)
  useTimerTitle(f.timer, TITLE, f.remaining, true)

  // The note shows once on this device. It counts as shown when it appears, like the other one-time offers.
  const [note, setNote] = useState(false)
  useEffect(() => {
    if (miniNoteSeen()) return
    setNote(true)
    markMiniNoteSeen()
  }, [])

  if (f.featureDisabled) return <Navigate to="/app/focus" replace />
  const focus = <PopOutFocus f={f} layout={layout} surface="mini_window" canGoBack={false} />
  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      {note ? <MiniWindowNote onDismiss={() => setNote(false)} /> : null}
      <div className="min-h-0 flex-1">
        {f.query.isPending ? (
          <p role="status" className="p-3 text-sm text-muted-foreground">
            Loading the timer
          </p>
        ) : trackerOn ? (
          <StopwatchOrFocus layout={layout} focus={focus} />
        ) : (
          focus
        )}
      </div>
    </div>
  )
}

/**
 * The fallback timer window, `/app/focus/mini` (X-01 W4.4): the timer in a small separate window for browsers without
 * Document Picture-in-Picture. It is its own page, so it runs its own timer read (the floating window instead borrows
 * the one the corner timer owns), and it keeps working if the tab that opened it closes. With the `floating_timer`
 * flag off it sends the student to the focus page.
 */
export function MiniWindowContainer() {
  const flagOn = useFeatureFlag('floating_timer')
  if (!flagOn) return <Navigate to="/app/focus" replace />
  return <MiniWindow />
}
