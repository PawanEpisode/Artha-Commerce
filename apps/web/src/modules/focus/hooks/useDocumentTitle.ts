import { useEffect } from 'react'

import { nowMs } from '~/modules/tracker'

import { tabTitle } from '../lib/timer-math'
import type { FocusTimer } from '../lib/types'

/**
 * The countdown in the browser tab ("24:12 Focus"), restored to the page title when the timer stops or the page closes.
 * `enabled` is false on the focus page, which sets the same title itself.
 */
export function useTimerTitle(timer: FocusTimer | null, base: string, seconds: number, enabled = true) {
  useEffect(() => {
    if (!enabled) return
    document.title = tabTitle(timer, nowMs(), base)
    return () => {
      document.title = base
    }
  }, [timer, base, seconds, enabled])
}
