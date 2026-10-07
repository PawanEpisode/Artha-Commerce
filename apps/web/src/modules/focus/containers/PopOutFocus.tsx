import { useState } from 'react'

import { nowMs } from '~/modules/tracker'

import { MiniTimerView } from '../components/MiniTimerView'
import { useContextLabel } from '../hooks/useContextLabel'
import type { FocusTimerApi } from '../hooks/useFocusTimer'
import { usePopOutSize } from '../hooks/usePopOutSize'
import { unlockAudio } from '../lib/chime'
import {
  END_CONFIRM_CONTROLS,
  nextStartBody,
  type PopoutContext,
  type PopoutControlId,
  popoutView,
  rememberContext,
  visibleControls,
} from '../lib/popout'
import { MIN_ROUND_SECONDS } from '../lib/presets'
import { elapsedSeconds } from '../lib/timer-math'

/** The browser can focus the opener tab from the window (spike S4.6). */
const CAN_GO_BACK = true

/**
 * The Pomodoro in the floating window. It draws the one `useFocusTimer` the corner timer owns and calls its actions, so
 * pausing here is pausing there; the controls are the focus page's, state by state (`popoutView`). Closing the window
 * never stops the timer.
 */
export function PopOutFocus({ f }: { f: FocusTimerApi }) {
  const { size, toggle } = usePopOutSize()
  const t = f.timer
  // The subject and chapter of the last round shown: what "Start round N" continues.
  const [remembered, setRemembered] = useState<PopoutContext | null>(null)
  const last = rememberContext(remembered, t)
  if (last !== remembered) setRemembered(last)
  // The round whose End is being confirmed: a new round or a closed one drops the question.
  const [endingId, setEndingId] = useState<string | null>(null)
  const ending = endingId !== null && endingId === t?.client_id

  const label = useContextLabel(last?.subject_id ?? null, last?.chapter_id ?? null)
  const view = popoutView(t, f.idle, null, nowMs(), last)
  const confirming = ending && view.controls.some((c) => c.id === 'end')
  const controls = visibleControls(confirming ? END_CONFIRM_CONTROLS : view.controls, size, CAN_GO_BACK)

  const act = (id: PopoutControlId) =>
    f.from('popout', () => {
      switch (id) {
        case 'pause':
          return f.pause()
        case 'resume':
          return f.resume()
        case 'extend':
          return f.extend()
        case 'skip_break':
          return f.skipBreak()
        case 'stop_save':
          return f.end(true)
        case 'claim_yes':
          return f.claim.mutate(true)
        case 'claim_no':
          return f.claim.mutate(false)
        case 'end':
          // Under a minute nothing is saved, so there is nothing to confirm.
          if (t && elapsedSeconds(t, nowMs()) < MIN_ROUND_SECONDS) return f.end(false)
          return setEndingId(t?.client_id ?? null)
        case 'save_end':
          setEndingId(null)
          return f.end(true)
        case 'discard':
          setEndingId(null)
          return f.end(false)
        case 'keep_going':
          return setEndingId(null)
        case 'start_next':
          if (!f.idle || !last || !f.settings) return
          unlockAudio()
          return f.start(nextStartBody(f.idle, last, f.settings), {
            has_subject: !!last.subject_id,
            resumed_cycle: true,
          })
        case 'back':
          return window.focus()
      }
    })

  return (
    <MiniTimerView
      variant={size}
      view={view}
      controls={controls}
      busy={f.busy}
      onControl={act}
      context={label}
      prompt={confirming ? 'End this round?' : undefined}
      announcement={f.announcement}
      onToggleSize={toggle}
    />
  )
}
