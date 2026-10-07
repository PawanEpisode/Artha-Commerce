import { useEffect } from 'react'

import { markActive } from '~/modules/tracker'

import { phaseTarget } from '../lib/popout'
import { recordPopoutTap, setPopoutOpen, setPopoutVisible, setPresenceTarget } from '../lib/popout-presence'
import type { FocusTimer } from '../lib/types'

/**
 * The presence rule for the fallback window (X-01 W4.4), the same one the floating window uses (`popoutAlive`) but
 * judged by this page's own visibility: it counts as open while it is on screen, and a tap in it after the round's
 * target keeps the extra time. When the window is hidden behind others the round end follows the normal away rules.
 */
export function useMiniWindowPresence(timer: FocusTimer | null) {
  useEffect(() => {
    setPopoutOpen(true)
    const sync = () => setPopoutVisible(document.visibilityState === 'visible')
    sync()
    const onTap = () => {
      markActive()
      recordPopoutTap()
    }
    document.addEventListener('visibilitychange', sync)
    window.addEventListener('pointerdown', onTap, true)
    window.addEventListener('keydown', onTap, true)
    return () => {
      document.removeEventListener('visibilitychange', sync)
      window.removeEventListener('pointerdown', onTap, true)
      window.removeEventListener('keydown', onTap, true)
      setPopoutOpen(false)
    }
  }, [])

  useEffect(() => {
    setPresenceTarget(phaseTarget(timer))
  }, [timer])
}
