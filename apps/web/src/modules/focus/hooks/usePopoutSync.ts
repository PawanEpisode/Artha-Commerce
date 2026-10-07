import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { track } from '~/modules/observability'
import { nowMs } from '~/modules/tracker'

import { focusKeys } from '../lib/keys'
import { advanceRound, phaseTarget, type PopoutRound } from '../lib/popout'
import { setPresenceTarget } from '../lib/popout-presence'
import { HEARTBEAT_SECONDS } from '../lib/presets'
import type { FocusTimer } from '../lib/types'
import { usePopOut } from './usePopOut'

/** A read older than this is overdue: the page's own timers did not fire (a hidden tab throttles them). */
const OVERDUE_MS = (HEARTBEAT_SECONDS + 1) * 1000
const WATCH_EVERY_MS = 2000

/**
 * Everything the floating window needs from the one timer owner (X-01 W4.2), apart from drawing:
 *
 * - tells the presence rule when the running phase reaches its target;
 * - keeps the 20 second heartbeat going from the window's own timers when the page's were throttled, so a round read
 *   from the window is still seen by the server (S4.3);
 * - reports `popout_session` once per focus round that had the window open.
 *
 * `reachedTarget` is passed in so the round report notices the moment a round passes its target.
 */
export function usePopoutSync(timer: FocusTimer | null, reachedTarget: boolean) {
  const qc = useQueryClient()
  const { window: win, isOpen } = usePopOut()

  useEffect(() => {
    setPresenceTarget(phaseTarget(timer))
  }, [timer])

  const live = timer !== null
  useEffect(() => {
    if (!win || !live) return
    const id = win.setInterval(() => {
      const updated = qc.getQueryState(focusKeys.timer)?.dataUpdatedAt ?? 0
      if (Date.now() - updated >= OVERDUE_MS)
        void qc.refetchQueries({ queryKey: focusKeys.timer }, { cancelRefetch: false })
    }, WATCH_EVERY_MS)
    return () => win.clearInterval(id)
  }, [win, live, qc])

  const round = useRef<PopoutRound | null>(null)
  useEffect(() => {
    const { next, report } = advanceRound(round.current, timer, isOpen, nowMs())
    round.current = next
    if (report) track('popout_session', { ...report })
  }, [timer, isOpen, reachedTarget])
}
