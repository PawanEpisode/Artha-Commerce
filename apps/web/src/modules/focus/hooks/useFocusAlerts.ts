import { useEffect, useRef, useState } from 'react'

import { track } from '~/modules/observability'

import { describeTransition } from '../lib/alerts'
import { playChime } from '../lib/chime'
import type { FocusSettings, FocusTimer } from '../lib/types'

/**
 * Tells the student a phase ended, in every channel they have allowed: a chime, a browser notification when the tab
 * is hidden, vibration on phones, and a polite live-region message for screen readers. `quiet` marks changes the
 * student caused themselves (ending early, skipping), which are not announced.
 */
export function useFocusAlerts(
  timer: FocusTimer | null,
  settings: FocusSettings | undefined,
  quiet: { current: boolean },
) {
  const prev = useRef<FocusTimer | null>(null)
  const [announcement, setAnnouncement] = useState('')

  useEffect(() => {
    const before = prev.current
    prev.current = timer
    if (quiet.current) {
      quiet.current = false
      return
    }
    const alert = describeTransition(before, timer)
    if (!alert || !settings) return
    setAnnouncement(`${alert.title}. ${alert.body}`)
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
      document.visibilityState === 'hidden'
    ) {
      try {
        new Notification(alert.title, { body: alert.body, tag: 'artha-focus' })
      } catch {
        // some browsers only allow notifications from a service worker
      }
    }
  }, [timer, settings, quiet])

  return announcement
}

/** Asks for the browser's notification permission and reports the answer. */
export async function requestNotifications(): Promise<'granted' | 'denied' | 'default' | 'unsupported'> {
  if (typeof Notification === 'undefined') return 'unsupported'
  const result = await Notification.requestPermission()
  track('focus_notification_permission', { result })
  return result
}
