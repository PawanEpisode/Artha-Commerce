import { track } from '~/modules/observability'

import type { AlertsResult } from './alertsStep'
import type { Environment } from './platform'
import type { Channel, ClickInfo, PermissionSource } from './schemas'

/** Web events of PRD section 10 (`noun_verb`). Properties never carry endpoints, keys, ids or notification text. */
export const NOTIFICATION_EVENTS = {
  permissionPrompted: 'push_permission_prompted',
  permissionResult: 'push_permission_result',
  testRequested: 'push_test_requested',
  deviceRemoved: 'push_device_removed',
  prefChanged: 'notification_pref_changed',
  pushClicked: 'push_clicked',
  inboxOpened: 'inbox_opened',
  alertsStepViewed: 'alerts_step_viewed',
  alertsStepCompleted: 'alerts_step_completed',
  localAlertShown: 'local_alert_shown',
  digestOfferShown: 'digest_offer_shown',
  digestAnswered: 'digest_answered',
} as const

export type PermissionResult = 'granted' | 'denied' | 'dismissed'

const where = (environment: Pick<Environment, 'platform' | 'displayMode'>) => ({
  platform: environment.platform,
  display_mode: environment.displayMode,
})

export const notificationAnalytics = {
  /** The onboarding step was shown; `branch` says which screen (PRD 5.1). */
  alertsStepViewed: (branch: string, environment: Pick<Environment, 'platform' | 'displayMode'>) =>
    track(NOTIFICATION_EVENTS.alertsStepViewed, { branch, ...where(environment) }),
  /** The step finished with `result` (granted, denied, dismissed, skipped_install, blocked, unsupported). */
  alertsStepCompleted: (result: AlertsResult, environment: Pick<Environment, 'platform' | 'displayMode'>) =>
    track(NOTIFICATION_EVENTS.alertsStepCompleted, { result, ...where(environment) }),
  /** A browser notification was shown from this tab. With the shared `tag` it proves one alert, not two (FR-N5). */
  localAlertShown: (tag: string) => track(NOTIFICATION_EVENTS.localAlertShown, { tag }),
  /** The browser prompt is about to show. */
  permissionPrompted: (source: PermissionSource) => track(NOTIFICATION_EVENTS.permissionPrompted, { source }),
  permissionResult: (result: PermissionResult, source: PermissionSource) =>
    track(NOTIFICATION_EVENTS.permissionResult, { result, source }),
  testRequested: (platform: string) => track(NOTIFICATION_EVENTS.testRequested, { platform }),
  deviceRemoved: (platform: string) => track(NOTIFICATION_EVENTS.deviceRemoved, { platform }),
  prefChanged: (change: { category: string; channel: Channel; enabled: boolean }) =>
    track(NOTIFICATION_EVENTS.prefChanged, {
      category: change.category,
      channel: change.channel,
      enabled: change.enabled,
    }),
  /** Only the fields the API returned are sent; a missing one is left out rather than guessed. */
  pushClicked: (info: ClickInfo) =>
    track(NOTIFICATION_EVENTS.pushClicked, {
      ...(info.category === undefined ? {} : { category: info.category }),
      ...(info.seconds_since_sent === undefined ? {} : { seconds_since_sent: info.seconds_since_sent }),
    }),
  /** An inbox item was opened (PRD section 10). Only the category and the age leave the page, never the text. */
  inboxOpened: (info: { category: string; seconds_since_sent: number }) =>
    track(NOTIFICATION_EVENTS.inboxOpened, { category: info.category, seconds_since_sent: info.seconds_since_sent }),
  /** The "switch to a daily digest" card was shown (W3.7). */
  digestOfferShown: (place: 'settings' | 'inbox') => track(NOTIFICATION_EVENTS.digestOfferShown, { place }),
  /** The student answered it, or switched the digest off again. */
  digestAnswered: (answer: 'accept' | 'decline' | 'stop', place: 'settings' | 'inbox') =>
    track(NOTIFICATION_EVENTS.digestAnswered, { answer, place }),
}
