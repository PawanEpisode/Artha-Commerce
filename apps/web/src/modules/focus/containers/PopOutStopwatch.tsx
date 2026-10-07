import { nowMs, type useStopwatch } from '~/modules/tracker'

import { MiniTimerView } from '../components/MiniTimerView'
import { useContextLabel } from '../hooks/useContextLabel'
import { usePopOutSize } from '../hooks/usePopOutSize'
import { popoutView, visibleControls } from '../lib/popout'
import type { WindowLayout } from './PopOutFocus'

type Stopwatch = ReturnType<typeof useStopwatch>

/** The stopwatch in the floating window: elapsed time and Pause or Resume, from the one `useStopwatch` the corner owns. */
export function PopOutStopwatch({
  sw,
  layout,
  canGoBack = true,
}: {
  sw: Stopwatch
  layout?: WindowLayout
  canGoBack?: boolean
}) {
  const remembered = usePopOutSize()
  const size = layout?.size ?? remembered.size
  const toggle = layout ? layout.onToggleSize : remembered.toggle
  const running = sw.stopwatch
  const label = useContextLabel(running?.subject_id ?? null, running?.chapter_id ?? null)
  if (!running) return null
  const view = popoutView(null, null, { paused: running.status === 'paused', seconds: sw.seconds }, nowMs(), null)
  return (
    <MiniTimerView
      variant={size}
      view={view}
      controls={visibleControls(view.controls, size, canGoBack)}
      busy={sw.busy}
      onControl={(id) => sw.toggle.mutate(id === 'resume' ? 'resume' : 'pause')}
      context={label}
      onToggleSize={toggle}
      fillParent={layout?.fillParent}
    />
  )
}
