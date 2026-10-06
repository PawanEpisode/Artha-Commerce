import { useEffect, useState } from 'react'

import { track } from '~/modules/observability'

import { HOLD_CAP_MS, isWakeLockSupported, type KeepAwakeStatus } from '../lib/wakeLock'

/**
 * Holds the Screen Wake Lock while `want` is true (FR-K1 to K3, K6).
 *
 * - Requests when `want` turns on and releases when it turns off (pause, end, phase end, away).
 * - The browser releases the lock whenever the tab is hidden, so the hook asks again when the tab is visible again.
 * - A refusal (low battery, battery saver, policy) is not an error: the status becomes `sleep` and nothing else
 *   changes. The timer never depends on the lock.
 * - One hold lasts at most four hours; after that the lock is released and not asked for again until `want` restarts.
 */
export function useWakeLock(want: boolean): KeepAwakeStatus {
  const supported = isWakeLockSupported()
  const [held, setHeld] = useState<boolean | null>(null)

  useEffect(() => {
    if (!want || !isWakeLockSupported()) {
      setHeld(null)
      return
    }
    let cancelled = false
    let capped = false
    let pending = false
    let refusedReported = false
    let sentinel: WakeLockSentinel | null = null

    const acquire = async () => {
      if (cancelled || capped || pending || sentinel || document.visibilityState !== 'visible') return
      pending = true
      try {
        const next = await navigator.wakeLock.request('screen')
        if (cancelled || capped) {
          void next.release().catch(() => undefined)
          return
        }
        sentinel = next
        next.addEventListener('release', () => {
          if (sentinel === next) {
            sentinel = null
            if (!cancelled) setHeld(false)
          }
        })
        setHeld(true)
      } catch {
        if (!cancelled) setHeld(false)
        if (!refusedReported) {
          refusedReported = true
          track('keep_awake_refused', {})
        }
      } finally {
        pending = false
      }
    }

    const onVisible = () => {
      if (document.visibilityState === 'visible') void acquire()
    }
    document.addEventListener('visibilitychange', onVisible)

    const cap = window.setTimeout(() => {
      capped = true
      const current = sentinel
      sentinel = null
      void current?.release().catch(() => undefined)
      setHeld(false)
      track('keep_awake_capped', {})
    }, HOLD_CAP_MS)

    void acquire()
    return () => {
      cancelled = true
      window.clearTimeout(cap)
      document.removeEventListener('visibilitychange', onVisible)
      const current = sentinel
      sentinel = null
      void current?.release().catch(() => undefined)
    }
  }, [want])

  if (!supported) return 'unsupported'
  if (!want) return 'off'
  if (held === null) return 'checking'
  return held ? 'held' : 'sleep'
}
