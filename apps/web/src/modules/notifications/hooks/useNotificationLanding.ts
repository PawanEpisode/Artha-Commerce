import { useLocation, useRouter } from '@tanstack/react-router'
import { useEffect } from 'react'

import { notificationAnalytics } from '../lib/analytics'
import { postClick } from '../lib/api'
import {
  alreadyReported,
  markReported,
  readNotificationId,
  takeLandingId,
  withoutNotificationParam,
} from '../lib/landing'

/**
 * `?n=<id>` (FR-N28): tells the API the student opened that notification, once, then removes the parameter from the
 * address. The id was captured when the app first loaded (the router may drop unknown parameters before this runs).
 * Failure is silent: the click is a nicety, never a reason to interrupt someone who just wants to study.
 */
export function useNotificationLanding() {
  const router = useRouter()
  const search = useLocation({ select: (location) => location.searchStr })

  useEffect(() => {
    const strip = () => {
      const next = withoutNotificationParam(window.location)
      if (next) router.history.replace(next)
    }
    const id = takeLandingId() ?? readNotificationId(window.location.search)
    if (!id) return
    if (alreadyReported(id)) {
      strip()
      return
    }
    markReported(id)
    void postClick(id)
      .then((info) => notificationAnalytics.pushClicked(info))
      .catch(() => undefined)
      .finally(strip)
  }, [search, router])
}
