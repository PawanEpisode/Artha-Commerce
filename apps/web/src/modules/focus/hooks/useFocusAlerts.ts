import { useCallback, useEffect, useRef, useState } from 'react'

import { reportLocalAlert, timerAlertTag } from '~/modules/notifications'
import { track } from '~/modules/observability'

import { type Alert, describeTransition, TARGET_REACHED } from '../lib/alerts'
import { playChime } from '../lib/chime'
import { alertClaimKey, claimAlert, otherWindowVisible, WINDOW_ID } from '../lib/cross-window'
import { notify } from '../lib/notify'
import type { FocusSettings, FocusTimer } from '../lib/types'
import { useWindowVisibility } from './useWindowVisibility'

/** Used only when a timer has no id to tag by (should not happen). */
export const FALLBACK_TAG = 'artha-focus'

/**
 * Tells the student a phase ended, in every channel they have allowed: a chime, a browser notification when the tab
 * is hidden, vibration on phones, and a polite live-region message for screen readers. `quiet` marks changes the
 * student caused themselves (ending early, skipping), which are not announced. With more than one Artha window open
 * (the fallback timer window, X-01 W4.4) the first window to claim a phase end plays the chime and shows the
 * notification; a notification is also skipped while any Artha window is visible.
 */
export function useFocusAlerts(
  timer: FocusTimer | null,
  settings: FocusSettings | undefined,
  quiet: { current: boolean },
) {
  useWindowVisibility()
  const prev = useRef<FocusTimer | null>(null)
  const [announcement, setAnnouncement] = useState('')
  // Focus rounds that ended by themselves during this visit: the moment a follow-up alerts ask may appear.
  const [roundsFinished, setRoundsFinished] = useState(0)

  // One delivery for every alert: a chime, a browser notification when the tab is hidden, vibration, a live region.
  const deliver = useCallback(
    (alert: Alert, ended: FocusTimer | null, kind: 'end' | 'target' = 'end') => {
      if (!settings) return
      const clientId = ended?.client_id ?? null
      setAnnouncement(`${alert.title}. ${alert.body}`)
      // Another window (or another hook in this one) already told the student about this phase end.
      if (ended && !claimAlert(alertClaimKey(ended.client_id, ended.version, kind))) return
      if (settings.sound_enabled) playChime(settings.volume)
      try {
        navigator.vibrate?.([200, 100, 200])
      } catch {
        // vibration is optional
      }
      if (
        settings.notifications_enabled &&
        typeof Notification !== 'undefined' &&
        Notification.permission === 'granted' &&
        document.visibilityState === 'hidden' &&
        !otherWindowVisible(WINDOW_ID)
      ) {
        // The tag is the one the push for this timer end carries (FR-N5), so a device that gets both shows one alert.
        const tag = clientId ? timerAlertTag(clientId) : FALLBACK_TAG
        try {
          new Notification(alert.title, { body: alert.body, tag })
          reportLocalAlert(tag)
        } catch {
          // some browsers only allow notifications from a service worker
        }
      }
    },
    [settings],
  )

  useEffect(() => {
    const before = prev.current
    prev.current = timer
    if (quiet.current) {
      quiet.current = false
      return
    }
    const alert = describeTransition(before, timer)
    if (!alert || !settings) return
    // The "did you finish?" question has its own dialog; a finished round or break gets a toast.
    if (timer === null || before?.client_id !== timer.client_id) notify.phaseEnded(alert)
    deliver(alert, before)
    if (before?.phase === 'focus' && timer?.client_id !== before.client_id) setRoundsFinished((n) => n + 1)
  }, [timer, settings, quiet, deliver])

  /** The planned length was reached and the round runs on: a toast and the same channels, but nothing ends. */
  const targetReached = useCallback(() => {
    notify.targetReached(TARGET_REACHED)
    deliver(TARGET_REACHED, prev.current, 'target')
  }, [deliver])

  return { announcement, targetReached, roundsFinished }
}

/** Asks for the browser's notification permission and reports the answer. */
export async function requestNotifications(): Promise<'granted' | 'denied' | 'default' | 'unsupported'> {
  if (typeof Notification === 'undefined') return 'unsupported'
  const result = await Notification.requestPermission()
  track('focus_notification_permission', { result })
  return result
}
