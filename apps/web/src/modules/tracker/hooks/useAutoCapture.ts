import { useEffect, useRef } from 'react'

import { useFeatureFlag } from '~/modules/observability'

import { newClientId, postAutoCapture } from '../lib/api'
import { createAccumulator } from '../lib/autoCapture'
import { markActive, nowMs, recentlyActive } from '../lib/clock'
import { useTrackerSettings } from './useTrackerQueries'

/**
 * Opt-in auto capture (off until the student turns it on in Tracker settings). While a syllabus chapter page is open,
 * visible and used, its active seconds are posted in short chunks as `source=auto` time. It is best effort: nothing is
 * queued offline, and a running timer or already recorded time simply wins on the server.
 */
export function useAutoCapture(chapterId: string | undefined) {
  const flag = useFeatureFlag('time_tracker')
  const optedIn = useTrackerSettings().data?.auto_capture_enabled === true
  const enabled = !!chapterId && flag && optedIn
  const acc = useRef(createAccumulator())

  useEffect(() => {
    if (!enabled || !chapterId) return
    const accumulator = acc.current
    const post = (chunk: { started_at: string; seconds: number } | null) => {
      if (chunk) void postAutoCapture({ client_id: newClientId(), chapter_id: chapterId, ...chunk }).catch(() => {})
    }
    const id = window.setInterval(
      () => post(accumulator.tick(nowMs(), document.visibilityState === 'visible' && recentlyActive())),
      1000,
    )
    const onHide = () => {
      if (document.visibilityState === 'hidden') post(accumulator.flush())
    }
    document.addEventListener('visibilitychange', onHide)
    const markers = ['pointerdown', 'keydown', 'pointermove', 'touchstart', 'scroll'] as const
    for (const e of markers) window.addEventListener(e, markActive, { passive: true })
    return () => {
      window.clearInterval(id)
      document.removeEventListener('visibilitychange', onHide)
      for (const e of markers) window.removeEventListener(e, markActive)
      post(accumulator.flush())
    }
  }, [enabled, chapterId])
}
