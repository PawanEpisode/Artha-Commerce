import { useEffect } from 'react'

import { nowMs } from '~/modules/tracker'

import { tabTitle } from '../lib/timer-math'
import type { FocusTimer } from '../lib/types'

/** The countdown in the browser tab ("24:12 Focus"), restored to the page title when the timer stops or the page closes. */
export function useTimerTitle(timer: FocusTimer | null, base: string, seconds: number) {
  useEffect(() => {
    document.title = tabTitle(timer, nowMs(), base)
    return () => {
      document.title = base
    }
  }, [timer, base, seconds])
}
