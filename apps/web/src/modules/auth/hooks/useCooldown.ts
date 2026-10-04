import { useCallback, useEffect, useState } from 'react'

import { RESEND_COOLDOWN_SECONDS, secondsRemaining } from '../lib/cooldown'

/** Countdown for "Resend code" buttons. `start()` begins a new cooldown. */
export function useCooldown(seconds: number = RESEND_COOLDOWN_SECONDS) {
  const [until, setUntil] = useState(0)
  const [left, setLeft] = useState(0)

  useEffect(() => {
    if (until === 0) return
    const tick = () => {
      const remaining = secondsRemaining(until, Date.now())
      setLeft(remaining)
      if (remaining === 0) clearInterval(timer)
    }
    const timer = setInterval(tick, 500)
    tick()
    return () => clearInterval(timer)
  }, [until])

  const start = useCallback(() => setUntil(Date.now() + seconds * 1000), [seconds])
  return { secondsLeft: left, active: left > 0, start }
}
