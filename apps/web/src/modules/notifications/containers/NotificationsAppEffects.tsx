import { useNotificationLanding } from '../hooks/useNotificationLanding'
import { useNotificationNavigation } from '../hooks/useNotificationNavigation'
import { usePushResync } from '../hooks/usePushResync'

/** Mounted once in the /app layout (signed in). Reports a notification click and keeps this device's record fresh. */
export function NotificationsAppEffects() {
  useNotificationLanding()
  useNotificationNavigation()
  usePushResync()
  return null
}
