import { describeEnvironment, type Environment } from './platform'

/** Browser permission for notifications, or `unsupported` when the API is missing. */
export type BrowserPermission = NotificationPermission | 'unsupported'

export const currentPermission = (): BrowserPermission =>
  typeof Notification === 'undefined' ? 'unsupported' : Notification.permission

const isStandalone = (): boolean => {
  try {
    const iosFlag = (navigator as Navigator & { standalone?: boolean }).standalone === true
    return iosFlag || window.matchMedia('(display-mode: standalone)').matches
  } catch {
    return false
  }
}

/** Reads the facts `describeEnvironment` needs from the real window. Client only. */
export function readEnvironment(): Environment {
  return describeEnvironment({
    userAgent: navigator.userAgent,
    maxTouchPoints: navigator.maxTouchPoints ?? 0,
    standalone: isStandalone(),
    hasServiceWorker: 'serviceWorker' in navigator,
    hasPushManager: typeof PushManager !== 'undefined',
    hasNotification: typeof Notification !== 'undefined',
    isSecureContext: window.isSecureContext,
  })
}
