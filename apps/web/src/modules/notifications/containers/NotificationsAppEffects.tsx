import { useNotificationLanding } from '../hooks/useNotificationLanding'
import { usePushResync } from '../hooks/usePushResync'

/** Mounted once in the /app layout (signed in). Reports a notification click and keeps this device's record fresh. */
export function NotificationsAppEffects() {
  useNotificationLanding()
  usePushResync()
  return null
}
