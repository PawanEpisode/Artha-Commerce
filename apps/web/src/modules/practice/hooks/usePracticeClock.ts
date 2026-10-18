import { useEffect, useState } from 'react'

import { type ClockSource, type PracticeClock, practiceClock } from '../lib/clock'

/**
 * The clock for one session, re-read every second. It is computed from the clock `source` each time, so a tab that was
 * asleep (browsers slow timers in the background) is correct the moment it wakes.
 */
export function usePracticeClock(source: ClockSource | null): PracticeClock | null {
  const [now, setNow] = useState(() => Date.now())
  const ticking = source !== null && (source.status === 'in_progress' || source.status === 'paused')

  useEffect(() => {
    if (!ticking) return
    const tick = () => setNow(Date.now())
    tick()
    const id = window.setInterval(tick, 1000)
    document.addEventListener('visibilitychange', tick)
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', tick)
    }
  }, [ticking])

  return source ? practiceClock(source, now) : null
}
