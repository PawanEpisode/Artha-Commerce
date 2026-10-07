import { useState } from 'react'

import { nowMs } from '~/modules/tracker'

import { MiniTimerView } from '../components/MiniTimerView'
import { useContextLabel } from '../hooks/useContextLabel'
import type { ActionSurface, FocusTimerApi } from '../hooks/useFocusTimer'
import { useOpenOnStart } from '../hooks/useOpenOnStart'
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
import type { PopOutSize } from '../lib/types'

/**
 * How the window is laid out when it is not the floating window: the fallback window picks its layout from its own
 * size and has no size toggle (the student resizes it).
 */
export interface WindowLayout {
  size: PopOutSize
  onToggleSize?: () => void
  /** Fill the parent instead of the whole window (the fallback window has a note above the timer). */
  fillParent?: boolean
}

interface Props {
  f: FocusTimerApi
  /** Absent in the floating window, whose size toggle and memory come from `usePopOutSize`. */
  layout?: WindowLayout
  /** Where actions are reported from (`phase_end_acknowledged.surface`). */
  surface?: Extract<ActionSurface, 'popout' | 'mini_window'>
  /** "Back to Artha": the browser can focus the opener tab from the floating window (spike S4.6), not from a pop-up. */
  canGoBack?: boolean
}

/**
 * The Pomodoro in the floating window. It draws the one `useFocusTimer` the corner timer owns and calls its actions, so
 * pausing here is pausing there; the controls are the focus page's, state by state (`popoutView`). Closing the window
 * never stops the timer.
 */
export function PopOutFocus({ f, layout, surface = 'popout', canGoBack = true }: Props) {
  const pipSize = usePopOutSize()
  const size = layout?.size ?? pipSize.size
  const toggle = layout ? layout.onToggleSize : pipSize.toggle
  const openOnStart = useOpenOnStart(f.settings)
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
  const controls = visibleControls(confirming ? END_CONFIRM_CONTROLS : view.controls, size, canGoBack)

  const act = (id: PopoutControlId) =>
    f.from(surface, () => {
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
          openOnStart()
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
      fillParent={layout?.fillParent}
    />
  )
}
