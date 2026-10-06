import { notificationAnalytics } from './analytics'

/**
 * One `tag` per timer end (FR-N5). The API builds the same string for the push (`domain/copy.py`, `timer:<client_id>`)
 * and the service worker passes it to `showNotification`, so a local alert and a push for the same moment replace each
 * other instead of stacking. Change both sides together.
 */
export const timerAlertTag = (clientId: string): string => `timer:${clientId}`

/** Tell analytics a local alert was shown (`local_alert_shown`), so a duplicate next to the push is visible in data. */
export const reportLocalAlert = (tag: string): void => notificationAnalytics.localAlertShown(tag)
