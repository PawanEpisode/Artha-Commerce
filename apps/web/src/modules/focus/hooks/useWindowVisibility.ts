import { useEffect } from 'react'

import { reportWindowVisible, VISIBLE_REFRESH_MS, WINDOW_ID } from '../lib/cross-window'

/**
 * Tells the other Artha windows of this browser whether this one is visible, so a window that is hidden does not show
 * a notification for something the student can see in another. Safe to mount more than once: they all write one record.
 */
export function useWindowVisibility() {
  useEffect(() => {
    const report = () => reportWindowVisible(WINDOW_ID, document.visibilityState === 'visible')
    report()
    const id = window.setInterval(report, VISIBLE_REFRESH_MS)
    const leave = () => reportWindowVisible(WINDOW_ID, false)
    document.addEventListener('visibilitychange', report)
    window.addEventListener('pagehide', leave)
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', report)
      window.removeEventListener('pagehide', leave)
    }
  }, [])
}
